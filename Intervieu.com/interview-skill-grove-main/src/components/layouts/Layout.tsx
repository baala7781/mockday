
import React from 'react';
import { Outlet } from 'react-router-dom';
import Navigation from '../Navigation';

const Layout: React.FC = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navigation />
      <main className="pt-20">
        {/* pt-20 accounts for fixed header height (py-4 + content) */}
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
