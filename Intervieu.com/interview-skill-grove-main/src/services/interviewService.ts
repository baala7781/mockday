/**
 * Service for communicating with the interview backend API (FastAPI)
 */
import { getAuth } from 'firebase/auth';

export interface StartInterviewRequest {
  user_id: string;
  role: 'frontend-developer' | 'backend-developer' | 'fullstack-developer' | 'data-scientist' | 'devops-engineer';
  resume_id?: string;
  resume_text?: string;
}

export interface StartInterviewResponse {
  interview_id: string;
  first_question: {
    question_id: string;
    question: string;
    skill: string;
    difficulty: string;
    question_type: string;
    context?: any;
  };
  estimated_duration: string;
  skill_weights: Array<{
    skill: string;
    weight: number;
    role_relevance: number;
  }>;
}

export interface SubmitAnswerRequest {
  answer: string;
  code?: string;
  language?: string;
}

export interface Evaluation {
  score: number;
  feedback: string;
  strengths: string[];
  weaknesses: string[];
  next_difficulty: string;
}

export interface AnswerResponse {
  evaluation: Evaluation;
  next_question?: {
    question_id: string;
    question: string;
    skill: string;
    difficulty: string;
    question_type: string;
    context?: any;
  };
  progress: {
    total_questions: number;
    questions_answered: number;
    current_phase: string;
    percentage: number;
  };
  completed: boolean;
}

export interface InterviewStatus {
  interview_id: string;
  status: string;
  progress: {
    total_questions: number;
    questions_answered: number;
    current_phase: string;
    percentage: number;
  };
  current_question?: {
    question_id: string;
    question: string;
    skill: string;
    difficulty: string;
    question_type: string;
    context?: any;
  };
}

// Base URL for API - use proxy in development
const getApiUrl = () => {
  // In development, use the Vite proxy
  if (import.meta.env.DEV) {
    return '/api'; // Will be proxied to backend by Vite
  }
  // In production, use the actual backend URL from environment
  const apiUrl = import.meta.env.VITE_API_URL;
  if (apiUrl) {
    // Ensure it's an absolute URL
    let url = apiUrl.trim();
    // Remove any leading/trailing slashes
    url = url.replace(/^\/+|\/+$/g, '');
    // Add https:// if not present
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `https://${url}`;
    }
    // Remove trailing slash and add /api if not present
    url = url.replace(/\/$/, '');
    if (!url.endsWith('/api')) {
      url = `${url}/api`;
    }
    return url;
  }
  // Fallback (should not happen in production)
  return '/api';
};

// Get WebSocket URL
const getWebSocketUrl = (interviewId: string) => {
  // In development, connect directly to local backend
  if (import.meta.env.DEV) {
    return `ws://localhost:8002/ws/interview/${interviewId}`;
  }
  
  // In production, use environment variable or construct from API URL
  const wsUrl = import.meta.env.VITE_WS_URL;
  if (wsUrl) {
    // If VITE_WS_URL is set, use it directly (should include wss://)
    return `${wsUrl}/ws/interview/${interviewId}`;
  }
  
  // Fallback: construct from API URL
  const apiUrl = import.meta.env.VITE_API_URL || '';
  if (apiUrl) {
    // Ensure it's an absolute URL
    let url = apiUrl.trim();
    // Remove any leading/trailing slashes
    url = url.replace(/^\/+|\/+$/g, '');
    // Add https:// if not present
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `https://${url}`;
    }
    // Convert https:// to wss:// or http:// to ws://
    const wsBase = url.replace('https://', 'wss://').replace('http://', 'ws://');
    return `${wsBase}/ws/interview/${interviewId}`;
  }
  
  // Last resort fallback
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${window.location.host}/ws/interview/${interviewId}`;
};

// Get authentication token
const getAuthToken = async (): Promise<string | null> => {
  try {
    const auth = getAuth();
    const user = auth.currentUser;
    if (user) {
      return await user.getIdToken();
    }
    return null;
  } catch (error) {
    console.error('Error getting auth token:', error);
    return null;
  }
};

export const interviewService = {
  /**
   * Start a new interview session
   */
  async startInterview(params: StartInterviewRequest): Promise<StartInterviewResponse> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(params),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to start interview' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error starting interview:', error);
      throw error;
    }
  },

  /**
   * Submit an answer and get the next question (REST API - for fallback)
   */
  async submitAnswer(interviewId: string, answer: SubmitAnswerRequest): Promise<AnswerResponse> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/${interviewId}/answer`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(answer),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to submit answer' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error submitting answer:', error);
      throw error;
    }
  },

  /**
   * Get interview status
   */
  async getInterviewStatus(interviewId: string): Promise<InterviewStatus> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/${interviewId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get interview status' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting interview status:', error);
      throw error;
    }
  },

  /**
   * Get WebSocket URL for interview
   */
  getWebSocketUrl(interviewId: string): string {
    return getWebSocketUrl(interviewId);
  },

  /**
   * End an interview manually (user clicked End Call)
   */
  async endInterview(interviewId: string): Promise<{ status: string; message: string; interview_id: string }> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/${interviewId}/end`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to end interview' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error ending interview:', error);
      throw error;
    }
  },

  /**
   * Get temporary Deepgram API key for client-side STT
   */
  async getDeepgramToken(interviewId: string): Promise<{ api_key: string; expires_in: number; model: string; language: string }> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/${interviewId}/deepgram-token`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get Deepgram token' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error: any) {
      console.error('Error getting Deepgram token:', error);
      throw error;
    }
  },

  /**
   * Get interview report
   */
  async getInterviewReport(interviewId: string): Promise<any> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/interviews/${interviewId}/report`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 202) {
          // Report is being generated
          throw new Error('Report is being generated. Please try again in a few moments.');
        }
        const error = await response.json().catch(() => ({ detail: 'Failed to get report' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.report;
    } catch (error) {
      console.error('Error getting report:', error);
      throw error;
    }
  },

  /**
   * Get all interviews for the current user
   */
  async getInterviews(): Promise<any[]> {
    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('User not authenticated');
      }

      const apiUrl = getApiUrl();
      // getApiUrl() already returns URL with /api suffix, so just append the endpoint
      const url = `${apiUrl}/interviews`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      // Check if response is HTML (error page)
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('text/html')) {
        const html = await response.text();
        console.error('Received HTML instead of JSON:', html.substring(0, 200));
        throw new Error(`Server returned HTML instead of JSON. Status: ${response.status}. Check API URL configuration.`);
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get interviews' }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting interviews:', error);
      throw error;
    }
  },
};

// Generate a unique session ID (legacy - not used with new API)
export const generateSessionId = (): string => {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
};
