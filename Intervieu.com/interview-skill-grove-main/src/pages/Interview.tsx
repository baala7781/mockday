
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import InterviewInterface from '../components/InterviewInterface';

const Interview: React.FC = () => {
  const [searchParams] = useSearchParams();
  const interviewId = searchParams.get('interviewId');

  if (!interviewId) {
    return (
      <div className="h-screen w-screen bg-background overflow-hidden flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground mb-2">Interview ID Required</h1>
          <p className="text-muted-foreground">Please start an interview from the dashboard.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-background overflow-hidden">
      <InterviewInterface interviewId={interviewId} />
    </div>
  );
};

export default Interview;
