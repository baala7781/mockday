
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import EmailVerificationGuard from './EmailVerificationGuard';

const ProtectedRoute: React.FC = () => {
  const { currentUser, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-8 w-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  // Allow access to verify-email page without verification
  if (location.pathname === '/verify-email') {
    return <Outlet />;
  }

  // For interview pages, show warning but allow access (users might be in middle of interview)
  if (location.pathname.startsWith('/interview')) {
    return (
      <EmailVerificationGuard showWarning={true}>
        <Outlet />
      </EmailVerificationGuard>
    );
  }

  // For other pages, require verification but allow skip
  return (
    <EmailVerificationGuard showWarning={false}>
      <Outlet />
    </EmailVerificationGuard>
  );
};

export default ProtectedRoute;
