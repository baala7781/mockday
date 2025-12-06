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

async function authedFetch(path: string, token: string, init?: RequestInit) {
  const res = await fetch(path, {
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
  const res = await authedFetch('/api/profile', token)
  return res.json()
}

export async function updateProfile(token: string, data: Partial<UserProfile>): Promise<void> {
  await authedFetch('/api/profile', token, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function getResumes(token: string): Promise<ResumeMeta[]> {
  const res = await authedFetch('/api/resumes', token)
  return res.json()
}

export async function addResume(token: string, meta: ResumeMeta): Promise<void> {
  await authedFetch('/api/resumes', token, {
    method: 'POST',
    body: JSON.stringify(meta),
  })
}

export async function uploadResume(token: string, file: File): Promise<{ status: string; resume: { id: string; name: string; parsed: boolean; skills: string[]; projects: string[] } }> {
  const formData = new FormData()
  formData.append('file', file)
  
  const res = await fetch('/api/resumes/upload', {
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



