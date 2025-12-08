
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { auth } from '../firebase'; // We will create this file next
import { onAuthStateChanged, User } from 'firebase/auth';
import { getProfile, getResumes } from '@/lib/api';

interface AuthContextType {
  currentUser: User | null;
  loading: boolean;
  profile: any | null;
  resumes: any[];
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<any | null>(null);
  const [resumes, setResumes] = useState<any[]>([]);

  // Fetch profile and resumes - accepts optional user to avoid stale closure
  const fetchProfileAndResumes = useCallback(async (user: User | null) => {
    if (!user) {
      setProfile(null);
      setResumes([]);
      return;
    }

    try {
      const token = await user.getIdToken();
      const [profileData, resumesData] = await Promise.all([
        getProfile(token),
        getResumes(token)
      ]);
      setProfile(profileData);
      setResumes(resumesData);
    } catch (error) {
      console.error('❌ Error fetching profile/resumes:', error);
      // Non-blocking - continue even if fetch fails
    }
  }, []);

  // Public refresh function that uses current user from state
  const refreshProfile = useCallback(async () => {
    await fetchProfileAndResumes(currentUser);
  }, [currentUser, fetchProfileAndResumes]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setCurrentUser(user);
      setLoading(false);
      
      // Fetch profile and resumes immediately when user is authenticated
      // Use the user parameter directly to avoid stale closure issues
      if (user) {
        await fetchProfileAndResumes(user);
      } else {
        setProfile(null);
        setResumes([]);
      }
    });

    return unsubscribe; // Cleanup subscription on unmount
  }, [fetchProfileAndResumes]);

  const value = {
    currentUser,
    loading,
    profile,
    resumes,
    refreshProfile,
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};
