import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import './App.css'
import { getVideos, startProcessing, getTaskStatus, VideoResponse, ProcessingStatus } from './services/api'

function App() {
  const [videos, setVideos] = useState<VideoResponse[]>([])
  const [playlistId, setPlaylistId] = useState('')
  const [loading, setLoading] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(() => {
    // Retrieve taskId from localStorage on initial load
    return localStorage.getItem('currentTaskId')
  })
  const [status, setStatus] = useState<ProcessingStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastProcessedCount, setLastProcessedCount] = useState(0)

  // Load videos on initial mount
  useEffect(() => {
    fetchVideos()
  }, [])

  // Store taskId in localStorage whenever it changes
  useEffect(() => {
    if (taskId) {
      localStorage.setItem('currentTaskId', taskId)
    } else {
      localStorage.removeItem('currentTaskId')
    }
  }, [taskId])

  // Poll for task status when a task is running
  useEffect(() => {
    if (!taskId) return

    const fetchStatus = async () => {
      try {
        const status = await getTaskStatus(taskId)
        setStatus(status)
        
        // Refresh videos list when new videos are processed
        if (status.processed_count > lastProcessedCount) {
          setLastProcessedCount(status.processed_count)
          fetchVideos()
        }
        
        // Stop polling when processing is complete
        if (status.message === "Processing complete.") {
          // Clear taskId from state and localStorage
          setTaskId(null)
          setLastProcessedCount(0)
          // Refresh video list
          fetchVideos()
        }
      } catch (err) {
        console.error('Error fetching task status:', err)
        // If the server doesn't recognize the task ID, clear it
        if ((err as any)?.response?.status === 404) {
          setTaskId(null)
          setLastProcessedCount(0)
        }
      }
    }

    // Fetch immediately on mount/taskId change
    fetchStatus()

    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [taskId, lastProcessedCount])

  // Auto-refresh video list on a regular interval when processing is happening
  useEffect(() => {
    if (!status || status.message === "Processing complete.") return;
    
    const intervalId = setInterval(() => {
      console.log("Auto-refreshing video list during processing...");
      fetchVideos();
    }, 5000);
    
    return () => clearInterval(intervalId);
  }, [status]);

  const fetchVideos = async () => {
    try {
      setLoading(true)
      const data = await getVideos()
      setVideos(data)
      setError(null)
    } catch (err) {
      console.error('Error fetching videos:', err)
      setError('Failed to load videos. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handleProcessPlaylist = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!playlistId.trim()) return

    try {
      setLoading(true)
      const response = await startProcessing(playlistId)
      setTaskId(response.task_id)
      setLastProcessedCount(0)
      setError(null)
    } catch (err) {
      console.error('Error starting processing:', err)
      setError('Failed to start processing. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-container">
      <header>
        <h1>YouTube Transcript Analyzer</h1>
      </header>
      
      <main>
        <section className="input-section">
          <form onSubmit={handleProcessPlaylist}>
            <input
              type="text"
              value={playlistId}
              onChange={(e) => setPlaylistId(e.target.value)}
              placeholder="Enter YouTube Playlist ID"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !playlistId.trim()}>
              Process Playlist
            </button>
          </form>
        </section>

        {error && <div className="error-message">{error}</div>}
        
        {status && (
          <section className="status-section">
            <h2>Processing Status</h2>
            <div className="status-details">
              <p><strong>Status:</strong> {status.message}</p>
              <p><strong>Processed:</strong> {status.processed_count}</p>
              <p><strong>Skipped:</strong> {status.skipped_count}</p>
              <p><strong>Failed:</strong> {status.failed_count}</p>
              {status.current_video_title && (
                <p><strong>Current Video:</strong> {status.current_video_title}</p>
              )}
            </div>
          </section>
        )}
        
        <section className="videos-section">
          <h2>Processed Videos</h2>
          {loading && !status ? (
            <p>Loading videos...</p>
          ) : videos.length > 0 ? (
            <div className="video-grid">
              {videos.map((video) => (
                <div key={video.videoId} className="video-card">
                  <h3>{video.title}</h3>
                  <div className="video-info">
                    <p>{video.analysis?.core_topic || 'No analysis available'}</p>
                    {video.analysis?.verdict && (
                      <p className={`verdict ${video.analysis.verdict.includes('Worth') ? 'worth-watching' : 'summary-sufficient'}`}>
                        {video.analysis.verdict}
                      </p>
                    )}
                  </div>
                  <a 
                    href={`https://youtube.com/watch?v=${video.videoId}`} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="video-link"
                  >
                    Watch on YouTube
                  </a>
                  <Link 
                    to={`/videos/${video.videoId}`} 
                    className="details-link"
                  >
                    View Analysis
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <p>No videos have been processed yet.</p>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
