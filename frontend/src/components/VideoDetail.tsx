import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getVideoDetail, VideoDetailResponse } from '../services/api';
import './VideoDetail.css';

interface VideoDetailProps {
  videoId: string;
}

export default function VideoDetail({ videoId }: VideoDetailProps) {
  const [video, setVideo] = useState<VideoDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'analysis' | 'transcript'>('analysis');
  const [isProcessing, setIsProcessing] = useState(false);

  const fetchVideoDetail = async () => {
    try {
      setLoading(true);
      const data = await getVideoDetail(videoId);
      console.log("Fetched video data:", data);
      console.log("Categories:", data.analysis?.categories);
      setVideo(data);
      
      // Consider the video to be in processing state if it has a transcript but no analysis
      setIsProcessing(data.has_transcript && !data.analysis?.core_topic);
      
      setError(null);
    } catch (err) {
      console.error('Error fetching video details:', err);
      setError('Failed to load video details. Please try again later.');
      setIsProcessing(false);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchVideoDetail();
  }, [videoId]);

  // Refresh while processing
  useEffect(() => {
    if (!isProcessing) return;
    
    // Set a more frequent refresh interval when processing (every 2 seconds)
    const intervalId = setInterval(() => {
      console.log('Refreshing video data during processing...');
      fetchVideoDetail();
    }, 2000); // Check every 2 seconds instead of 5
    
    return () => clearInterval(intervalId);
  }, [isProcessing, videoId]);

  if (loading && !video) {
    return <div className="loading">Loading video details...</div>;
  }

  if (error && !video) {
    return <div className="error-message">{error}</div>;
  }

  if (!video) {
    return <div className="error-message">Video not found</div>;
  }

  // Convert takeaways and categories to markdown lists if they exist
  const takeawaysMarkdown = video.analysis?.takeaways?.length 
    ? video.analysis.takeaways.map(item => `* ${item}`).join('\n')
    : '';

  // Get categories as a properly-typed array
  const getCategories = (): string[] => {
    if (!video.analysis?.categories) {
      console.log("No categories found in video.analysis");
      return [];
    }
    
    console.log("Raw categories data:", video.analysis.categories);
    
    // If categories is already an array, use it
    if (Array.isArray(video.analysis.categories)) {
      console.log("Categories is an array with length:", video.analysis.categories.length);
      return video.analysis.categories.map(cat => String(cat)); // Ensure all items are strings
    }
    
    // If it's a string, try to parse it
    if (typeof video.analysis.categories === 'string') {
      const categoriesStr = video.analysis.categories as string;
      if (!categoriesStr.trim()) {
        console.log("Categories is an empty string");
        return [];
      }
      
      // First, check if it's a JSON string
      try {
        const parsed = JSON.parse(categoriesStr);
        console.log("Successfully parsed JSON categories:", parsed);
        if (Array.isArray(parsed)) {
          return parsed.map(cat => String(cat)); // Ensure all items are strings
        }
        return [String(parsed)]; // If it's a single value, wrap in array
      } catch (e) {
        // Not JSON, try comma-separated string
        console.log("Not JSON, trying comma-separated string");
        const splitCategories = categoriesStr.split(',').map(item => item.trim());
        console.log("Split by comma result:", splitCategories);
        return splitCategories.filter(c => c.length > 0);
      }
    }
    
    console.log("Categories has unknown format, returning empty array");
    return [];
  };

  const categories = getCategories();
  console.log("Processed categories:", categories);

  return (
    <div className="video-detail-container">
      <header className="video-detail-header">
        <h1>{video.title}</h1>
        <div className="video-actions">
          <a 
            href={`https://youtube.com/watch?v=${video.videoId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="watch-button"
          >
            Watch on YouTube
          </a>
          <Link to="/" className="back-button">Back to List</Link>
        </div>
      </header>

      {isProcessing && (
        <div className="processing-notice">
          <div className="processing-icon"></div>
          <div className="processing-message">
            <h3>Analysis in Progress</h3>
            <p>Gemini AI is analyzing this video transcript. The analysis will appear automatically when complete.</p>
            <p className="note">This page refreshes automatically. You can safely leave this tab open.</p>
          </div>
        </div>
      )}

      <div className="tab-navigation">
        <button 
          className={activeTab === 'analysis' ? 'active' : ''}
          onClick={() => setActiveTab('analysis')}
        >
          Analysis {isProcessing && '(Processing...)'}
        </button>
        <button 
          className={activeTab === 'transcript' ? 'active' : ''}
          onClick={() => setActiveTab('transcript')}
        >
          Transcript
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'analysis' ? (
          <div className="analysis-content">
            {video.analysis ? (
              <>
                <section className="analysis-section">
                  <h2>Core Topic & Purpose</h2>
                  <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {video.analysis.core_topic || 'No core topic available'}
                    </ReactMarkdown>
                  </div>
                </section>

                <section className="analysis-section">
                  <h2>Summary</h2>
                  <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {video.analysis.summary || 'No summary available'}
                    </ReactMarkdown>
                  </div>
                </section>

                {video.analysis.structure && (
                  <section className="analysis-section">
                    <h2>Structure</h2>
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {video.analysis.structure}
                      </ReactMarkdown>
                    </div>
                  </section>
                )}

                {video.analysis.takeaways && video.analysis.takeaways.length > 0 && (
                  <section className="analysis-section">
                    <h2>Key Takeaways</h2>
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {takeawaysMarkdown}
                      </ReactMarkdown>
                    </div>
                  </section>
                )}

                {categories.length > 0 && (
                  <section className="analysis-section">
                    <h2>Categories</h2>
                    <div className="categories-list">
                      {categories.map((category, index) => (
                        <span key={index} className="category-tag">{category}</span>
                      ))}
                    </div>
                  </section>
                )}

                {video.analysis.verdict && (
                  <section className="analysis-section verdict-section">
                    <h2>Watch Value Assessment</h2>
                    <div className={`verdict ${video.analysis.verdict.includes('Worth') ? 'worth-watching' : 'summary-sufficient'}`}>
                      {video.analysis.verdict}
                    </div>
                    {video.analysis.justification && (
                      <div className="justification markdown-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {video.analysis.justification}
                        </ReactMarkdown>
                      </div>
                    )}
                  </section>
                )}
              </>
            ) : (
              <p className="no-analysis">
                {isProcessing 
                  ? 'Analysis is being generated. Please wait...' 
                  : 'No analysis available for this video.'}
              </p>
            )}
          </div>
        ) : (
          <div className="transcript-content">
            {video.transcript ? (
              <pre className="transcript-text">{video.transcript}</pre>
            ) : (
              <p className="no-transcript">No transcript available for this video.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
} 