#!/usr/bin/env python3
"""
Ingest documents using Docling and store in PostgreSQL vector store.
This script processes documents and creates a contextual RAG system.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

from llama_index.core import VectorStoreIndex
from llama_index.core import Document as LlamaDocument
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.readers.docling import DoclingReader

def get_database_config():
    """Get database configuration from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    parsed = urlparse(database_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port,
        'database': parsed.path.lstrip('/'),
        'user': parsed.username,
        'password': parsed.password
    }

def setup_embedding_model():
    """Initialize the Ollama embedding model."""
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaEmbedding(
        model_name="nomic-embed-text", 
        base_url=ollama_base_url,
        embed_batch_size=1,  # Reduce batch size to avoid timeouts
        request_timeout=120  # Reduce timeout
    )

def ingest_documents():
    """Main function to ingest documents."""
    print("🚀 Starting document ingestion...")
    
    # Setup paths
    data_dir = project_root / "data"
    raw_dir = data_dir / "raw"
    
    if not raw_dir.exists():
        print(f" Raw data directory not found: {raw_dir}")
        print("Please ensure you have documents in the data/raw directory")
        return False
    
    # Get database config
    try:
        db_config = get_database_config()
        print(f"Database config loaded for {db_config['host']}:{db_config['port']}")
    except Exception as e:
        print(f" Database configuration error: {e}")
        return False
    
    # Setup embedding model
    try:
        embed_model = setup_embedding_model()
        # Test the embedding model first
        test_embed = embed_model.get_text_embedding("test")
        print(f"Embedding model initialized (dim: {len(test_embed)})")
    except Exception as e:
        print(f" Embedding model error: {e}")
        return False
    
    # Initialize DoclingReader
    try:
        reader = DoclingReader()
        print("DoclingReader initialized")
    except Exception as e:
        print(f" DoclingReader error: {e}")
        return False
    
    # Load documents
    try:
        print(f"📂 Loading documents from {raw_dir}")
        documents = []
        
        # Get all PDF and DOCX files
        file_patterns = ['*.pdf', '*.PDF', '*.docx', '*.DOCX']
        files_to_process = []
        
        for pattern in file_patterns:
            files_to_process.extend(raw_dir.glob(pattern))
        
        print(f"Found {len(files_to_process)} files to process")
        
        # Process each file
        for file_path in files_to_process:
            print(f"Processing: {file_path.name}")
            file_docs = reader.load_data(file_path=str(file_path))
            
            # Add filename metadata to each document
            for doc in file_docs:
                doc.metadata = doc.metadata or {}
                doc.metadata['source_file'] = file_path.name
                doc.metadata['file_path'] = str(file_path)
            
            documents.extend(file_docs)
            
        print(f"Loaded {len(documents)} documents from {len(files_to_process)} files")
        
        # Add metadata
        for i, doc in enumerate(documents):
            # Extract filename from metadata or generate one
            filename = getattr(doc, 'metadata', {}).get('file_name', f'doc_{i}')
            doc.metadata = doc.metadata or {}
            doc.metadata.update({
                'source_file': filename,
                'doc_id': f'doc_{i}',
                'ingestion_method': 'docling'
            })
            
    except Exception as e:
        print(f" Document loading error: {e}")
        return False
    
    # Setup vector store
    try:
        table_name = "doc_md_contextual_20250830"
        vector_store = PGVectorStore.from_params(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            table_name=table_name,
            embed_dim=768,  # nomic-embed-text dimension
            hybrid_search=True,
            text_search_config="english",
        )
        print(f"Vector store initialized with table: {table_name}")
    except Exception as e:
        print(f" Vector store error: {e}")
        return False
    
    # Create index and ingest documents
    try:
        print("Creating vector index and ingesting documents...")
        index = VectorStoreIndex.from_documents(
            documents,
            vector_store=vector_store,
            embed_model=embed_model,
            show_progress=True
        )
        print("Documents successfully ingested into vector store!")
        
        # Test the index
        print("🧪 Testing the index...")
        query_engine = index.as_query_engine()
        test_response = query_engine.query("What is this document about?")
        print(f"Test query result: {str(test_response)[:200]}...")
        
        return True
        
    except Exception as e:
        print(f" Document ingestion error: {e}")
        return False

if __name__ == "__main__":
    success = ingest_documents()
    if success:
        print("\n🎉 Document ingestion completed successfully!")
        print("Your documents are now indexed and ready for querying.")
    else:
        print("\n💥 Document ingestion failed!")
        sys.exit(1)