"""
ResQAI - Text Chunker
Splits documents into semantically meaningful chunks for RAG indexing.

Strategies:
- Recursive character splitting (default)
- Sentence-aware splitting
- Token-aware splitting (respects LLM context windows)
- Semantic splitting (split on topic changes)
"""

import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TextChunk:
    """A single chunk of text with metadata."""
    content: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    section_title: Optional[str] = None
    metadata: Optional[dict] = None


class RecursiveTextChunker:
    """
    Recursive character text splitter.
    Tries to split on paragraphs, then sentences, then words.
    Ensures chunks don't exceed max_tokens.

    This is the primary chunker for most document types.
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]

    def __init__(
        self,
        chunk_size: int = 512,       # Target tokens per chunk
        chunk_overlap: int = 64,     # Overlap tokens between consecutive chunks
        separators: Optional[List[str]] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS
        # Rough chars-per-token estimate (4 chars ≈ 1 token for English)
        self._chars_per_token = 4

    def chunk(self, text: str, metadata: Optional[dict] = None) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text to chunk
            metadata: Optional metadata attached to all chunks

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        max_chars = self.chunk_size * self._chars_per_token
        overlap_chars = self.chunk_overlap * self._chars_per_token

        raw_chunks = self._split_text(text, max_chars)
        chunks = []
        char_pos = 0

        for i, chunk_text in enumerate(raw_chunks):
            chunk_start = text.find(chunk_text, max(0, char_pos - overlap_chars))
            chunk_end = chunk_start + len(chunk_text)
            token_estimate = max(1, len(chunk_text) // self._chars_per_token)

            chunks.append(TextChunk(
                content=chunk_text.strip(),
                chunk_index=i,
                char_start=chunk_start,
                char_end=chunk_end,
                token_count=token_estimate,
                metadata=metadata,
            ))
            char_pos = chunk_end

        return [c for c in chunks if c.content]

    def _split_text(self, text: str, max_chars: int) -> List[str]:
        """Recursively split text using separator hierarchy."""
        for separator in self.separators:
            if separator == "":
                # Last resort: character-level split
                return [text[i: i + max_chars] for i in range(0, len(text), max_chars - (self.chunk_overlap * self._chars_per_token))]

            splits = text.split(separator)
            # Check if any split exceeds max_chars
            good_splits = []
            current = ""

            for split in splits:
                test = current + separator + split if current else split
                if len(test) <= max_chars:
                    current = test
                else:
                    if current:
                        good_splits.append(current)
                    # If single split is too long, recurse with next separator
                    if len(split) > max_chars:
                        remaining_seps = self.separators[self.separators.index(separator) + 1:]
                        sub_chunker = RecursiveTextChunker(
                            self.chunk_size, self.chunk_overlap, remaining_seps
                        )
                        good_splits.extend(sub_chunker._split_text(split, max_chars))
                    else:
                        current = split

            if current:
                good_splits.append(current)

            if len(good_splits) > 1:
                return good_splits

        return [text]


class MarkdownChunker(RecursiveTextChunker):
    """
    Markdown-aware chunker that respects heading structure.
    Splits on ## headings first, then delegates to parent.
    """

    def chunk(self, text: str, metadata: Optional[dict] = None) -> List[TextChunk]:
        """Split markdown text respecting heading hierarchy."""
        # Extract sections by heading
        sections = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
        all_chunks = []
        current_section = ""
        chunk_idx = 0

        for part in sections:
            if re.match(r"^#{1,3}\s+", part):
                current_section = part.strip()
            else:
                combined = f"{current_section}\n\n{part}" if current_section else part
                sub_chunks = super().chunk(combined, metadata)
                for chunk in sub_chunks:
                    chunk.chunk_index = chunk_idx
                    chunk.section_title = current_section or None
                    all_chunks.append(chunk)
                    chunk_idx += 1

        return all_chunks if all_chunks else super().chunk(text, metadata)


class SentenceChunker:
    """
    Sentence-aware chunker that groups complete sentences.
    Better for QA tasks where answers span multiple sentences.
    """

    def __init__(self, sentences_per_chunk: int = 5, overlap_sentences: int = 1) -> None:
        self.sentences_per_chunk = sentences_per_chunk
        self.overlap = overlap_sentences

    def chunk(self, text: str, metadata: Optional[dict] = None) -> List[TextChunk]:
        """Split text into chunks of complete sentences."""
        # Simple sentence tokenization
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        chunks = []
        step = max(1, self.sentences_per_chunk - self.overlap)

        for i in range(0, len(sentences), step):
            window = sentences[i: i + self.sentences_per_chunk]
            content = " ".join(window)
            chunks.append(TextChunk(
                content=content,
                chunk_index=len(chunks),
                char_start=text.find(window[0]) if window else 0,
                char_end=text.find(window[-1]) + len(window[-1]) if window else 0,
                token_count=max(1, len(content) // 4),
                metadata=metadata,
            ))

        return chunks


def get_chunker_for_content_type(content_type: str) -> RecursiveTextChunker:
    """
    Select appropriate chunker based on document type.

    Args:
        content_type: Document type identifier

    Returns:
        Appropriate chunker instance
    """
    if content_type in ("fssai_regulation", "who_guideline", "government_notification"):
        # Regulatory docs: larger chunks to preserve context
        return RecursiveTextChunker(chunk_size=1024, chunk_overlap=128)
    elif content_type in ("ngo_profile", "restaurant_profile"):
        # Profile docs: small chunks for precise retrieval
        return RecursiveTextChunker(chunk_size=256, chunk_overlap=32)
    elif content_type == "donation_history":
        # History: sentence-level for specific fact retrieval
        return SentenceChunker(sentences_per_chunk=3, overlap_sentences=1)
    else:
        # Default: balanced chunks
        return RecursiveTextChunker(chunk_size=512, chunk_overlap=64)
