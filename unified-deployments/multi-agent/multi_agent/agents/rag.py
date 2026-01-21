"""
RAG Agent - Retrieval-Augmented Generation for knowledge tasks.

Handles document retrieval, knowledge base queries, and factual Q&A.
"""

from typing import Optional, List, Dict, Any
from ..core import Agent, Result

RAG_INSTRUCTIONS = """You are a RAG (Retrieval-Augmented Generation) Agent specialized in knowledge retrieval and factual information.

Your capabilities:
1. Search and retrieve relevant documents from the knowledge base
2. Answer questions based on retrieved context
3. Synthesize information from multiple sources
4. Cite sources and provide references

Guidelines:
- Always search the knowledge base before answering factual questions
- Clearly distinguish between retrieved facts and your own reasoning
- If information is not found, acknowledge the limitation
- Provide source citations when available
- For complex queries, break them into sub-queries

You have access to the following tools:
- search_knowledge_base: Search for relevant documents
- get_document: Retrieve a specific document by ID
- summarize_documents: Summarize multiple documents

When you cannot find relevant information, be honest about it and suggest alternative approaches."""


class RAGAgent:
    """Factory for creating RAG agents with retrieval capabilities."""
    
    def __init__(
        self,
        model: str = "gpt-oss-20b",
        milvus_host: str = "milvus",
        milvus_port: int = 19530,
        collection_name: str = "knowledge_base",
        embedding_model: str = "text-embedding-3-small",
    ):
        self.model = model
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._milvus_client = None
        
    def _get_milvus_client(self):
        """Lazy initialization of Milvus client."""
        if self._milvus_client is None:
            try:
                from pymilvus import MilvusClient
                self._milvus_client = MilvusClient(
                    uri=f"http://{self.milvus_host}:{self.milvus_port}"
                )
            except Exception as e:
                import structlog
                structlog.get_logger().warning("milvus_connection_failed", error=str(e))
                self._milvus_client = None
        return self._milvus_client
        
    def _create_rag_functions(self) -> list:
        """Create RAG tool functions."""
        
        def search_knowledge_base(query: str, top_k: int = 5) -> str:
            """
            Search the knowledge base for relevant documents.
            
            Args:
                query: Search query text
                top_k: Number of results to return (default: 5)
            """
            client = self._get_milvus_client()
            if client is None:
                return "Knowledge base is currently unavailable. Please try again later."
            
            try:
                # In production, you'd embed the query and search
                # For now, return a placeholder
                results = client.search(
                    collection_name=self.collection_name,
                    data=[query],  # Would be embeddings in production
                    limit=top_k,
                    output_fields=["text", "source", "metadata"],
                )
                
                if not results or not results[0]:
                    return f"No relevant documents found for query: {query}"
                
                formatted_results = []
                for i, hit in enumerate(results[0], 1):
                    text = hit.get("entity", {}).get("text", "No content")
                    source = hit.get("entity", {}).get("source", "Unknown")
                    score = hit.get("distance", 0)
                    formatted_results.append(
                        f"[{i}] (Score: {score:.3f}) Source: {source}\n{text[:500]}..."
                    )
                
                return "\n\n".join(formatted_results)
                
            except Exception as e:
                return f"Error searching knowledge base: {str(e)}"
        
        def get_document(document_id: str) -> str:
            """
            Retrieve a specific document by its ID.
            
            Args:
                document_id: Unique identifier of the document
            """
            client = self._get_milvus_client()
            if client is None:
                return "Knowledge base is currently unavailable."
            
            try:
                results = client.get(
                    collection_name=self.collection_name,
                    ids=[document_id],
                )
                
                if not results:
                    return f"Document not found: {document_id}"
                
                doc = results[0]
                return f"Document: {document_id}\nSource: {doc.get('source', 'Unknown')}\n\n{doc.get('text', 'No content')}"
                
            except Exception as e:
                return f"Error retrieving document: {str(e)}"
        
        def summarize_documents(document_ids: str) -> str:
            """
            Summarize multiple documents.
            
            Args:
                document_ids: Comma-separated list of document IDs
            """
            ids = [d.strip() for d in document_ids.split(",")]
            summaries = []
            
            for doc_id in ids[:5]:  # Limit to 5 documents
                content = get_document(doc_id)
                summaries.append(f"--- {doc_id} ---\n{content[:1000]}")
            
            return "\n\n".join(summaries)
        
        return [search_knowledge_base, get_document, summarize_documents]
    
    def create(self) -> Agent:
        """Create the RAG agent with retrieval functions."""
        return Agent(
            name="RAG Agent",
            model=self.model,
            instructions=RAG_INSTRUCTIONS,
            functions=self._create_rag_functions(),
        )


def create_rag_agent(
    model: str = "gpt-oss-20b",
    milvus_host: str = "milvus",
    milvus_port: int = 19530,
    collection_name: str = "knowledge_base",
) -> Agent:
    """
    Create a RAG agent with knowledge retrieval capabilities.
    
    Args:
        model: Model to use for the RAG agent
        milvus_host: Milvus vector database host
        milvus_port: Milvus port
        collection_name: Name of the Milvus collection
        
    Returns:
        Configured RAG Agent
    """
    factory = RAGAgent(
        model=model,
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        collection_name=collection_name,
    )
    return factory.create()
