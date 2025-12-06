export interface UserProfile {
  name?: string
  email?: string
  location?: string
  experienceLevel?: string
  linkedinUrl?: string
  bio?: string
  experiences?: any[]
  educations?: any[]
  skills?: string[]
  createdAt?: string
  updatedAt?: string
}

export interface ResumeMeta {
  id: string
  name: string
  storagePath?: string
  url?: string
  uploadedAt?: string
}

// Get API base URL - use backend URL in production, proxy in development
const getApiBaseUrl = () => {
  if (import.meta.env.DEV) {
    return '/api'; // Vite proxy in development
  }
  const apiUrl = import.meta.env.VITE_API_URL;
  if (apiUrl) {
    // Ensure it's an absolute URL
    let url = apiUrl.trim();
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
  return '/api';
};

async function authedFetch(path: string, token: string, init?: RequestInit) {
  const baseUrl = getApiBaseUrl();
  // Ensure path starts with / and remove /api prefix if present (baseUrl already has /api)
  let cleanPath = path.startsWith('/') ? path : `/${path}`;
  // Remove /api prefix if path already has it (avoid double /api/api)
  if (cleanPath.startsWith('/api')) {
    cleanPath = cleanPath.replace(/^\/api/, '');
  }
  // Ensure cleanPath starts with /
  if (!cleanPath.startsWith('/')) {
    cleanPath = `/${cleanPath}`;
  }
  const fullPath = `${baseUrl}${cleanPath}`;
  
  const res = await fetch(fullPath, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
    credentials: 'include',
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(msg || `Request failed: ${res.status}`)
  }
  return res
}

export async function getProfile(token: string): Promise<UserProfile> {
  const res = await authedFetch('/profile', token)
  return res.json()
}

export async function updateProfile(token: string, data: Partial<UserProfile>): Promise<void> {
  await authedFetch('/profile', token, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function getResumes(token: string): Promise<ResumeMeta[]> {
  const res = await authedFetch('/resumes', token)
  return res.json()
}

export async function addResume(token: string, meta: ResumeMeta): Promise<void> {
  await authedFetch('/resumes', token, {
    method: 'POST',
    body: JSON.stringify(meta),
  })
}

export async function uploadResume(token: string, file: File): Promise<{ status: string; resume: { id: string; name: string; parsed: boolean; skills: string[]; projects: string[] } }> {
  const formData = new FormData()
  formData.append('file', file)
  
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/resumes/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    credentials: 'include',
    body: formData,
  })
  
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(msg || `Request failed: ${res.status}`)
  }
  
  return res.json()
}



