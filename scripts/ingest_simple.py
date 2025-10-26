#!/usr/bin/env python3
"""
Simple document ingestion using processed markdown files.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

from llama_index.core import VectorStoreIndex, Document
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding

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

def ingest_from_processed():
    """Ingest from pre-processed markdown files."""
    print("🚀 Starting simple document ingestion from processed markdown...")
    
    # Setup paths
    data_dir = project_root / "data"
    md_dir = data_dir / "processed" / "md"
    
    if not md_dir.exists():
        print(f" Processed markdown directory not found: {md_dir}")
        return False
    
    # Get database config
    try:
        db_config = get_database_config()
        print(f"Database config loaded for {db_config['host']}:{db_config['port']}")
    except Exception as e:
        print(f" Database configuration error: {e}")
        return False
    
    # Setup embedding model with simpler config
    try:
        embed_model = OllamaEmbedding(
            model_name="nomic-embed-text",
            base_url="http://localhost:11434",
            embed_batch_size=1
        )
        print("Embedding model initialized")
    except Exception as e:
        print(f" Embedding model error: {e}")
        return False
    
    # Load markdown documents
    try:
        documents = []
        md_files = list(md_dir.glob("*.md"))
        print(f"📂 Found {len(md_files)} markdown files")
        
        for md_file in md_files:
            content = md_file.read_text(encoding='utf-8')
            doc = Document(
                text=content,
                metadata={
                    'source_file': md_file.name,
                    'file_path': str(md_file),
                    'ingestion_method': 'simple_md'
                }
            )
            documents.append(doc)
            
        print(f"Loaded {len(documents)} documents")
        
    except Exception as e:
        print(f" Document loading error: {e}")
        return False
    
    # Setup vector store
    try:
        table_name = "doc_md_simple_20250830"
        vector_store = PGVectorStore.from_params(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            table_name=table_name,
            embed_dim=768,
            hybrid_search=True,
            text_search_config="english",
        )
        print(f"Vector store initialized with table: {table_name}")
    except Exception as e:
        print(f" Vector store error: {e}")
        return False
    
    # Create index with smaller chunks
    try:
        print("Creating vector index and ingesting documents...")
        
        # Process one document at a time to avoid issues
        for i, doc in enumerate(documents):
            print(f"Processing document {i+1}/{len(documents)}: {doc.metadata['source_file']}")
            
            # Create small index for this document
            small_index = VectorStoreIndex.from_documents(
                [doc],
                vector_store=vector_store,
                embed_model=embed_model,
                show_progress=True
            )
            
        print("Documents successfully ingested into vector store!")
        
        # Test the index
        print("🧪 Testing the index...")
        final_index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
        query_engine = final_index.as_query_engine()
        test_response = query_engine.query("What documents are available?")
        print(f"Test query result: {str(test_response)[:200]}...")
        
        return True
        
    except Exception as e:
        print(f" Document ingestion error: {e}")
        return False

if __name__ == "__main__":
    success = ingest_from_processed()
    if success:
        print("\n🎉 Document ingestion completed successfully!")
        print("Your documents are now indexed and ready for querying.")
    else:
        print("\n💥 Document ingestion failed!")
        sys.exit(1)