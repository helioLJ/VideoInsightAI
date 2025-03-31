import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000', // Ensure this matches your backend URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Define interfaces matching backend schemas
interface VideoAnalysis {
  core_topic?: string;
  summary?: string;
  structure?: string;
  takeaways?: string[];
  categories?: string[];
  verdict?: string;
  justification?: string;
}

export interface VideoResponse {
  videoId: string;
  playlistId: string;
  title: string;
  fetch_timestamp_utc?: Date;
  analysis?: VideoAnalysis;
  has_transcript: boolean;
}

export interface VideoDetailResponse extends VideoResponse {
  transcript?: string;
}

export interface ProcessingStatus {
  message: string;
  processed_count: number;
  skipped_count: number;
  failed_count: number;
  current_video_id?: string;
  current_video_title?: string;
}

export const getVideos = async (): Promise<VideoResponse[]> => {
  const response = await apiClient.get<VideoResponse[]>('/videos/');
  return response.data;
};

export const getVideoDetail = async (videoId: string): Promise<VideoDetailResponse> => {
     const response = await apiClient.get<VideoDetailResponse>(`/videos/${videoId}`);
     return response.data;
 };

export const startProcessing = async (playlistId: string): Promise<{ message: string; task_id: string }> => {
  const response = await apiClient.post<{ message: string; task_id: string }>('/process/', { playlist_id: playlistId });
  return response.data;
};

export const getTaskStatus = async (taskId: string): Promise<ProcessingStatus> => {
     const response = await apiClient.get<ProcessingStatus>(`/status/${taskId}`);
     return response.data;
 };