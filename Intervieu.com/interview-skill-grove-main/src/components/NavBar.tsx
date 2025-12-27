
import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auth } from '../firebase';
import { signOut } from 'firebase/auth';

const NavBar: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { currentUser } = useAuth();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location]);
  
  const handleSignOut = async () => {
    try {
      await signOut(auth);
      navigate('/login'); // Redirect to login page after sign out
    } catch (error) {
      console.error("Failed to sign out:", error);
    }
  };

  const navLinks = [
    { name: 'Home', path: '/' },
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'Interview', path: '/interview' },
    { name: 'Report', path: '/report' },
  ];

  return (
    <header 
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-300 ${
        isScrolled || isMobileMenuOpen 
          ? 'bg-background/95 backdrop-blur-md shadow-sm border-b border-border' 
          : 'bg-transparent'
      }`}
    >
      <div className="page-container py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2">
          <div className="h-9 w-9 rounded-full bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-lg">M</span>
          </div>
          <span className="font-semibold text-xl">MockDay</span>
        </Link>

        {/* Desktop Menu */}
        <nav className="hidden md:flex items-center space-x-8">
          {navLinks.map((link) => (
            <Link
              key={link.name}
              to={link.path}
              className={`text-sm font-medium transition-colors hover:text-primary ${
                location.pathname === link.path ? 'text-primary' : 'text-foreground/80'
              }`}
            >
              {link.name}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center space-x-4">
          {currentUser ? (
            <>
              <span className="text-sm text-foreground/80 hidden lg:block">
                Welcome, {currentUser.displayName || currentUser.email}
              </span>
              <button onClick={handleSignOut} className="btn-outline py-2">
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn-outline py-2">
                Sign In
              </Link>
              <Link to="/signup" className="btn-primary py-2">
                Get Started
              </Link>
            </>
          )}
        </div>

        {/* Mobile Menu Toggle */}
        <button 
          className="md:hidden rounded-full p-2 hover:bg-accent/10"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden h-[calc(100vh-4rem)] bg-background/95 backdrop-blur-lg border-t border-border animate-in slide-in-from-top-5 duration-300">
          <nav className="flex flex-col space-y-6 p-6">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                to={link.path}
                className={`text-lg font-medium px-4 py-2 rounded-lg transition-colors ${
                  location.pathname === link.path 
                    ? 'bg-accent text-primary' 
                    : 'text-foreground hover:bg-accent/50'
                }`}
              >
                {link.name}
              </Link>
            ))}
            <div className="pt-4 flex flex-col space-y-4">
              {currentUser ? (
                <button onClick={handleSignOut} className="btn-outline w-full text-center">
                  Sign Out
                </button>
              ) : (
                <>
                  <Link to="/login" className="btn-outline w-full text-center">
                    Sign In
                  </Link>
                  <Link to="/signup" className="btn-primary w-full text-center">
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
};

export default NavBar;
