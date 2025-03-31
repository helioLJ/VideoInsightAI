import { useParams } from 'react-router-dom';
import VideoDetail from '../components/VideoDetail';

export default function VideoDetailPage() {
  const { videoId } = useParams<{ videoId: string }>();
  
  if (!videoId) {
    return <div className="error-message">Video ID is required</div>;
  }
  
  return <VideoDetail videoId={videoId} />;
} 