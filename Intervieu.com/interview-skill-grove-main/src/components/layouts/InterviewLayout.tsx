import React from 'react';
import { Outlet } from 'react-router-dom';

const InterviewLayout: React.FC = () => {
  return (
    <div className="fixed inset-0 bg-background text-foreground overflow-hidden">
      {/* No navigation/header - full screen interview experience */}
      {/* Fixed positioning ensures no scrolling and fits all screens */}
      <Outlet />
    </div>
  );
};

export default InterviewLayout;

