
import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { User, Bell, Lock, LogOut, Trash2 } from 'lucide-react';

const SettingsLayout: React.FC = () => {
  const navigation = [
    { name: 'Profile', href: '/profile', icon: User },
    { name: 'Notifications', href: '/profile/notifications', icon: Bell },
    { name: 'Security', href: '/profile/security', icon: Lock },
  ];

  const getLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
      isActive
        ? 'bg-primary/10 text-primary'
        : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
    }`;

  return (
    <div className="bg-muted/30 min-h-[calc(100vh-4rem)]"> {/* Adjust min-height to account for header */}
      <div className="page-container py-8">
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 gap-8">
          {/* Left Sidebar */}
          <aside className="md:col-span-1 lg:col-span-1">
            <div className="bg-card p-4 rounded-lg shadow-sm">
                <nav className="space-y-1">
                    {navigation.map((item) => (
                        <NavLink key={item.name} to={item.href} className={getLinkClass} end>
                            <item.icon className="h-5 w-5 mr-3" />
                            <span>{item.name}</span>
                        </NavLink>
                    ))}
                </nav>
                <div className="border-t border-border my-4"></div>
                <div className="space-y-1">
                    <NavLink to="/profile/signout" className={getLinkClass}>
                        <LogOut className="h-5 w-5 mr-3" />
                        <span>Sign Out</span>
                    </NavLink>
                    <NavLink to="/profile/delete-account" className={`${getLinkClass({isActive: false})} !text-red-500 hover:!bg-red-500/10`}>
                        <Trash2 className="h-5 w-5 mr-3" />
                        <span>Delete Account</span>
                    </NavLink>
                </div>
            </div>
          </aside>

          {/* Right Content Area */}
          <main className="md:col-span-3 lg:col-span-4">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};

export default SettingsLayout;
