-- schema.sql

-- 1. Parent Tables
CREATE TABLE VisualVideos (
  VideoId STRING(64) NOT NULL,
  Title STRING(MAX) NOT NULL,
  GcsUri STRING(1024) NOT NULL,
) PRIMARY KEY(VideoId);

CREATE TABLE TranscriptVideos (
  VideoId STRING(64) NOT NULL,
  Title STRING(MAX) NOT NULL,
  GcsUri STRING(1024) NOT NULL,
) PRIMARY KEY(VideoId);

-- 2. Child Tables (Interleaved)
CREATE TABLE VisualVideoSegments (
  VideoId STRING(64) NOT NULL,
  SegmentId INT64 NOT NULL,
  StartOffsetSec INT64 NOT NULL,
  EndOffsetSec INT64 NOT NULL,
  Embedding ARRAY<FLOAT64>(vector_length=>1408),
) PRIMARY KEY(VideoId, SegmentId),
  INTERLEAVE IN PARENT VisualVideos ON DELETE CASCADE;

CREATE TABLE VideoTranscripts (
  VideoId STRING(64) NOT NULL,
  TranscriptId INT64 NOT NULL,
  StartOffsetSec INT64 NOT NULL,
  EndOffsetSec INT64 NOT NULL,
  SubtitleText STRING(MAX) NOT NULL,
  SubtitleText_Tokens TOKENLIST AS (TOKENIZE_FULLTEXT(SubtitleText)) HIDDEN,
  Embedding ARRAY<FLOAT64>(vector_length=>768),
) PRIMARY KEY(VideoId, TranscriptId),
  INTERLEAVE IN PARENT TranscriptVideos ON DELETE CASCADE;

-- 3. High-Performance Indexes
CREATE VECTOR INDEX VisualSegmentEmbeddingIndex
ON VisualVideoSegments(Embedding)
WHERE Embedding IS NOT NULL
OPTIONS (distance_type = 'COSINE');

CREATE VECTOR INDEX TranscriptEmbeddingIndex
ON VideoTranscripts(Embedding)
WHERE Embedding IS NOT NULL
OPTIONS (distance_type = 'COSINE');

CREATE SEARCH INDEX TranscriptSearchIndex
ON VideoTranscripts(SubtitleText_Tokens);
