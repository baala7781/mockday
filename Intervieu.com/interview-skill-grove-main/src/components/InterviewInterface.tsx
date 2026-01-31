
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { User, Bot, Code, Settings, X, Phone, Mic, MicOff, Volume2, VolumeX, Loader2, AlertCircle } from 'lucide-react';
import VideoFeed from './ui/VideoFeed';
import { useToast } from "@/hooks/use-toast";
import { useInterviewWebSocket } from '@/hooks/useInterviewWebSocket';
import MarkdownRenderer from './ui/MarkdownRenderer';
import { interviewService } from '@/services/interviewService';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { javascript } from '@codemirror/lang-javascript';
import { java } from '@codemirror/lang-java';
import { cpp } from '@codemirror/lang-cpp';
import { oneDark } from '@codemirror/theme-one-dark';

interface TranscriptItem {
  speaker: 'Interviewer' | 'You';
  text: string;
  timestamp: Date;
}

interface InterviewInterfaceProps {
  interviewId: string;
}

// Helper function to get language extension
const getLanguageExtension = (language: string) => {
  switch (language) {
    case 'python':
      return python();
    case 'javascript':
    case 'typescript':
      return javascript({ jsx: true, typescript: language === 'typescript' });
    case 'java':
      return java();
    case 'cpp':
    case 'c':
      return cpp();
    default:
      return python();
  }
};

const InterviewInterface: React.FC<InterviewInterfaceProps> = ({ interviewId }) => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [isCodeEditorOpen, setIsCodeEditorOpen] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [codeAnswer, setCodeAnswer] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('python');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true); // Check if interview completed on load
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const codeEditorContainerRef = useRef<HTMLDivElement>(null);
  const [codeEditorHeight, setCodeEditorHeight] = useState(400);

  // Check interview status on mount - if completed, redirect to report
  useEffect(() => {
    const checkInterviewStatus = async () => {
      try {
        const status = await interviewService.getInterviewStatus(interviewId);
        if (status.status === 'completed') {
          toast({
            title: "Interview Already Completed",
            description: "Redirecting to your report...",
          });
          setTimeout(() => {
            navigate(`/interviews/${interviewId}/report`, { replace: true });
          }, 1000);
          return;
        }
      } catch (error) {
        console.error('Error checking interview status:', error);
      } finally {
        setIsCheckingStatus(false);
      }
    };
    
    checkInterviewStatus();
  }, [interviewId, navigate, toast]);
  
  // Interview WebSocket hook
  const {
    isConnected,
    isConnecting,
    error,
    currentQuestion,
    evaluation,
    progress,
    transcript: liveTranscript,
    isInterviewCompleted,
    isProcessingAnswer, // True when waiting for next question
    sendTextAnswer,
    sendCodeAnswer,
    startRecording,
    stopRecording,
    isRecording,
    audioLevel,
    isPlaying,
    volume,
    setVolume,
  } = useInterviewWebSocket({
    interviewId,
    onQuestion: (question) => {
      // When a new question arrives, clear any interim transcripts but keep final answers
      setTranscript(prev => {
        // Remove any interim transcripts (ending with "...")
        const cleaned = prev.filter(item => !(item.speaker === 'You' && item.text.endsWith('...')));
        // Add the new question
        return [...cleaned, {
          speaker: 'Interviewer',
          text: question.question,
          timestamp: new Date(),
        }];
      });
      
      // Auto-open code editor if coding question
      if (question.question_type === 'coding') {
        setIsCodeEditorOpen(true);
      }
      
      // Clear submitting state when new question arrives
      setIsSubmitting(false);
      
      // Scroll to bottom
      setTimeout(() => {
        transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    },
    onEvaluation: (evalData) => {
      // Don't show evaluation to candidate - evaluation is for backend/internal use only
      // Answer evaluated (not shown to candidate) - score, feedback, strengths, weaknesses
    },
    onTranscript: (text, isFinal) => {
      // Only show transcript when recording stops (isFinal = true)
      // This prevents multiple bubbles - single bubble per answer
      if (isFinal && text) {
        setTranscript(prev => {
          // Check if there's already a "You" item for this answer (shouldn't happen, but just in case)
          const hasRecentAnswer = prev.length > 0 && prev[prev.length - 1].speaker === 'You';
          
          if (!hasRecentAnswer) {
            // Add the answer as a single bubble
            return [...prev, {
              speaker: 'You',
              text: text,
              timestamp: new Date(),
            }];
          } else {
            // Update the last answer if it exists
            const updated = [...prev];
            updated[updated.length - 1] = {
              speaker: 'You',
              text: text,
              timestamp: new Date(),
            };
            return updated;
          }
        });
        
        // Scroll to bottom
        setTimeout(() => {
          transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      }
    },
    onCompleted: () => {
      toast({
        title: "Interview Completed",
        description: "Your interview has been completed. Redirecting to report...",
      });
      // Navigate to report page with interview ID in URL path
      setTimeout(() => {
        navigate(`/interviews/${interviewId}/report`);
      }, 2000);
    },
    onError: (errorMsg) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMsg,
      });
    },
    enableAudioRecording: true,
    enableAudioPlayback: true,
  });

  // Load initial question when connected (only if not already loaded via WebSocket)
  useEffect(() => {
    // Don't fetch via REST API - WebSocket will send the current question on connect
    // This prevents duplicate questions on reconnection
    if (isConnected && !currentQuestion) {
      // Wait a bit for WebSocket to send the question
      const timer = setTimeout(() => {
        // Only fetch if WebSocket didn't send a question after 1 second
        if (!currentQuestion) {
          interviewService.getInterviewStatus(interviewId)
            .then(status => {
              if (status.current_question && !currentQuestion) {
                // Only add if we still don't have a question
                setTranscript(prev => {
                  // Check if question already in transcript
                  const exists = prev.some(item => 
                    item.speaker === 'Interviewer' && 
                    item.text === status.current_question!.question
                  );
                  if (!exists) {
                    return [...prev, {
                      speaker: 'Interviewer',
                      text: status.current_question!.question,
                      timestamp: new Date(),
                    }];
                  }
                  return prev;
                });
              }
            })
            .catch(console.error);
        }
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isConnected, interviewId, currentQuestion]);

  // Scroll to bottom when transcript updates
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Calculate code editor height when it opens
  useEffect(() => {
    if (isCodeEditorOpen && codeEditorContainerRef.current) {
      const updateHeight = () => {
        if (codeEditorContainerRef.current) {
          const rect = codeEditorContainerRef.current.getBoundingClientRect();
          setCodeEditorHeight(rect.height - 20); // Subtract padding
        }
      };
      updateHeight();
      window.addEventListener('resize', updateHeight);
      return () => window.removeEventListener('resize', updateHeight);
    }
  }, [isCodeEditorOpen]);

  const handleEndInterview = async () => {
    if (isInterviewCompleted) {
      navigate(`/interviews/${interviewId}/report`);
      return;
    }

    try {
      // Call backend to properly end the interview and trigger report generation
      await interviewService.endInterview(interviewId);
      
      toast({
        title: "Interview Ended",
        description: "Your interview has been saved. Redirecting to report...",
      });
      
      // Navigate to report page (report will be generated by backend)
      setTimeout(() => {
        navigate(`/interviews/${interviewId}/report`, { replace: true });
      }, 1500);
    } catch (error) {
      console.error('Error ending interview:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to end interview properly. Your progress has been saved.",
      });
      navigate('/dashboard');
    }
  };

  const handleSubmitAnswer = async () => {
    if (!currentAnswer.trim() && !codeAnswer.trim()) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Please provide an answer or code.",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      if (isCodeEditorOpen && codeAnswer.trim()) {
        // Submit code answer - add to transcript first, then send
        const codeText = `\`\`\`${selectedLanguage}\n${codeAnswer}\n\`\`\``;
        setTranscript(prev => [...prev, {
          speaker: 'You',
          text: codeText,
          timestamp: new Date(),
        }]);
        sendCodeAnswer(codeAnswer, selectedLanguage);
        // DON'T clear: setCodeAnswer('');
        setIsCodeEditorOpen(false);
      } else if (currentAnswer.trim()) {
        // Submit text answer - add to transcript first, then send
        setTranscript(prev => [...prev, {
          speaker: 'You',
          text: currentAnswer,
          timestamp: new Date(),
        }]);
        sendTextAnswer(currentAnswer);
        setCurrentAnswer('');
      }
      // Note: isSubmitting will be reset when next question arrives or on error
      // Don't set to false immediately - let the WebSocket hook handle it
    } catch (error) {
      console.error('Error submitting answer:', error);
      setIsSubmitting(false);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to submit answer. Please try again.",
      });
    }
  };

  const handleSubmitCode = async () => {
    if (!codeAnswer.trim()) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Please write some code.",
      });
      return;
    }

    setIsSubmitting(true);
    
    try {
      // Add code to transcript first, then send
      const codeText = `\`\`\`${selectedLanguage}\n${codeAnswer}\n\`\`\``;
      setTranscript(prev => [...prev, {
        speaker: 'You',
        text: codeText,
        timestamp: new Date(),
      }]);
      sendCodeAnswer(codeAnswer, selectedLanguage);
      // DON'T clear code - let it stay for review
      // setCodeAnswer('');
      setIsCodeEditorOpen(false); // Close editor but keep code
      // Note: isSubmitting will be reset when next question arrives or on error
      // Don't set to false immediately - let the WebSocket hook handle it
    } catch (error) {
      console.error('Error submitting code:', error);
      setIsSubmitting(false);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to submit code. Please try again.",
      });
    }
  };

  // Progress is shown as "X of Y questions" instead of percentage

  // Show loading while checking interview status
  if (isCheckingStatus) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading interview...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex items-center justify-center p-4 md:p-6 bg-background overflow-hidden">
      <div className="w-full h-full max-w-screen-2xl grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 overflow-hidden" style={{ maxHeight: '100dvh' }}>

        {/* Left Column */}
        <div className="lg:col-span-1 flex flex-col gap-4 md:gap-6 h-full min-h-0 overflow-hidden">
          
          <Card className="flex flex-col items-center justify-center p-4 md:p-6 flex-shrink-0">
            <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Bot size={60} className="text-primary"/>
            </div>
            <h2 className="text-xl font-bold">AI Interviewer</h2>
            <div className="mt-2 flex items-center gap-2">
              {isConnected ? (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse"></div>
                  Connected
                </span>
              ) : isConnecting ? (
                <span className="text-xs text-yellow-600 flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Connecting...
                </span>
              ) : (
                <span className="text-xs text-red-600 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  Disconnected
                </span>
              )}
            </div>
          </Card>

          {/* Video feed disabled - commented out as per requirements */}
          {/* <div className="flex-1 min-h-0 overflow-hidden">
            <Card className="relative h-full flex items-center justify-center overflow-hidden">
               <VideoFeed mirrored={true} className="h-full w-full" />
               <div className="absolute bottom-2 left-2 text-xs bg-background/80 backdrop-blur-sm text-foreground px-2 py-0.5 rounded border border-border">You</div>
            </Card>
          </div> */}

          <Card className="flex-shrink-0">
            <CardHeader className='pb-3'><CardTitle className='text-base'>Interview Controls</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {/* Manual Recording Controls */}
              <div className="flex gap-2">
                <Button 
                  variant={isRecording ? "default" : "outline"} 
                  className={isRecording ? "bg-green-500 hover:bg-green-600" : ""}
                  onClick={() => startRecording()} 
                  disabled={isInterviewCompleted || isPlaying || !isConnected || isRecording || isProcessingAnswer}
                  title={isProcessingAnswer ? "Processing answer..." : "Start Answering"}
                >
                  <Mic className="mr-2 h-4 w-4" />
                  {isProcessingAnswer ? "Processing..." : "Start Answering"}
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => stopRecording()} 
                  disabled={isInterviewCompleted || !isRecording}
                  title="Stop Answering"
                >
                  <MicOff className="mr-2 h-4 w-4" />
                  Stop Answering
                </Button>
              </div>

              {/* Recording Indicator - Subtle pulse animation */}
              {isRecording && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-xs text-green-600 font-medium">Recording</span>
                  </div>
                </div>
              )}

              {/* Other Controls */}
              <div className="flex items-center justify-around pt-2 border-t">
                <Button 
                  variant={currentQuestion?.question_type === 'coding' ? "default" : "outline"}
                  size="icon" 
                  onClick={() => setIsCodeEditorOpen(true)} 
                  title="Code Editor"
                  disabled={isInterviewCompleted}
                  className={currentQuestion?.question_type === 'coding' ? "bg-primary text-primary-foreground" : ""}
                >
                  <Code size={20}/>
                </Button>
                <Button 
                  variant="outline" 
                  size="icon" 
                  onClick={() => setVolume(volume > 0 ? 0 : 1)}
                  title={volume > 0 ? "Mute" : "Unmute"}
                >
                  {volume > 0 ? <Volume2 size={20}/> : <VolumeX size={20}/>}
                </Button>
                <Button 
                  variant="destructive" 
                  size="icon" 
                  onClick={handleEndInterview} 
                  title="End Interview"
                >
                  <Phone size={20}/>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="flex-shrink-0">
            <CardContent className="pt-4 md:pt-6">
              <div className="flex justify-between items-center mb-2">
                  <p className="text-sm font-medium">Interview Progress</p>
              </div>
              {progress && (
                <div className="space-y-2 mt-2">
                  <div className="flex justify-between items-center">
                    <p className="text-xs text-muted-foreground">
                      Phase: {progress.current_phase.replace('_', ' ').toUpperCase()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {progress.questions_answered} of {progress.total_questions} questions
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Interview continues until {progress.total_questions} questions or 30 minutes
                  </p>
                  {isSubmitting && (
                    <p className="text-xs text-yellow-600 flex items-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Processing answer...
                    </p>
                  )}
                  {evaluation && !isSubmitting && (
                    <p className="text-xs text-green-600">
                      ✓ Answer received - Next question incoming...
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

        </div>

        {/* Right Column */}
        <div className="lg:col-span-2 bg-card border border-border rounded-2xl shadow-lg flex flex-col relative overflow-hidden h-full min-h-0">
            {isCodeEditorOpen && (
                <div className='fixed inset-0 bg-background z-50 flex flex-col md:flex-row'>
                  {/* Left Side: Question Display */}
                  <div className='w-full md:w-1/2 border-r border-border p-4 md:p-6 overflow-y-auto bg-slate-50 dark:bg-slate-900'>
                    <div className='flex justify-between items-center mb-4'>
                      <h2 className="text-xl md:text-2xl font-bold">Coding Challenge</h2>
                      <Button variant="ghost" size="icon" onClick={() => setIsCodeEditorOpen(false)}>
                        <X size={20}/>
                      </Button>
                    </div>
                    
                    {/* Question Display with Rich Formatting */}
                    <div className='bg-white dark:bg-slate-800 p-4 md:p-6 rounded-lg shadow-sm'>
                      <MarkdownRenderer 
                        content={currentQuestion?.question || 'Loading question...'}
                        className="text-sm md:text-base"
                      />
                    </div>
                  </div>
                  
                  {/* Right Side: Code Editor */}
                  <div className='w-full md:w-1/2 flex flex-col p-4 md:p-6 bg-slate-900'>
                    <div className='flex justify-between items-center mb-4'>
                      <div className="flex items-center gap-3">
                        <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                          <SelectTrigger className="w-[140px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="python">Python</SelectItem>
                            <SelectItem value="javascript">JavaScript</SelectItem>
                            <SelectItem value="typescript">TypeScript</SelectItem>
                            <SelectItem value="java">Java</SelectItem>
                            <SelectItem value="cpp">C++</SelectItem>
                          </SelectContent>
                        </Select>
                        <h3 className="font-semibold text-white">Your Solution</h3>
                      </div>
                    </div>
                    
                    <div className='flex-grow rounded-lg border border-border overflow-hidden' style={{minHeight: '400px'}}>
                      <CodeMirror
                        value={codeAnswer}
                        height="100%"
                        extensions={[getLanguageExtension(selectedLanguage)]}
                        theme={oneDark}
                        onChange={(value) => setCodeAnswer(value)}
                        className="h-full"
                        basicSetup={{
                          lineNumbers: true,
                          highlightActiveLineGutter: true,
                          highlightSpecialChars: true,
                          foldGutter: true,
                          drawSelection: true,
                          dropCursor: true,
                          allowMultipleSelections: true,
                          indentOnInput: true,
                          bracketMatching: true,
                          closeBrackets: true,
                          autocompletion: true,
                          rectangularSelection: true,
                          highlightActiveLine: true,
                          highlightSelectionMatches: true,
                        }}
                      />
                    </div>
                    
                    <div className="flex justify-end gap-2 mt-4">
                      <Button variant="outline" onClick={() => setIsCodeEditorOpen(false)}>Cancel</Button>
                      <Button 
                        onClick={handleSubmitCode}
                        disabled={isSubmitting || !codeAnswer.trim() || !isConnected}
                      >
                        {isSubmitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Submitting...</> : 'Submit Code'}
                      </Button>
                    </div>
                  </div>
                </div>
            )}

            <ScrollArea className="flex-1 min-h-0 p-4 md:p-6 pb-20 md:pb-6">
                <div className="space-y-4 md:space-y-6">
                    {transcript.length === 0 ? (
                      <div className="flex items-center justify-center h-full">
                        <div className="text-center text-muted-foreground">
                          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                          <p>Waiting for first question...</p>
                        </div>
                      </div>
                    ) : (
                      transcript.map((item, index) => (
                        <div key={index} className={`flex items-start gap-3 ${item.speaker === 'You' ? 'flex-row-reverse' : ''}`}>
                            <div className={`rounded-lg p-3 md:p-4 max-w-[80%] ${item.speaker === 'You' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                                {item.speaker === 'Interviewer' ? (
                                  <MarkdownRenderer 
                                    content={item.text}
                                    className="text-sm md:text-base"
                                  />
                                ) : (
                                  <div className="text-sm md:text-base whitespace-pre-wrap">
                                    {item.text}
                                  </div>
                                )}
                                <p className="text-xs opacity-70 mt-1">
                                  {item.timestamp.toLocaleTimeString()}
                                </p>
                            </div>
                        </div>
                      ))
                    )}
                    <div ref={transcriptEndRef} />
                </div>
            </ScrollArea>

            <div className="p-3 md:p-4 border-t bg-muted/50 flex-shrink-0 sticky bottom-0 z-10">
              {isInterviewCompleted ? (
                <div className="w-full text-center text-sm text-green-600 bg-green-50 p-2 rounded-lg">
                  Interview completed! Redirecting to report...
                </div>
              ) : currentQuestion ? (
                <div className="space-y-2">
                  <Textarea
                    placeholder="Type your answer here or speak into the microphone..."
                    value={currentAnswer}
                    onChange={(e) => setCurrentAnswer(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.ctrlKey) {
                        handleSubmitAnswer();
                      }
                    }}
                    className="min-h-[80px] max-h-[120px] resize-none"
                    disabled={isSubmitting || !isConnected}
                    onFocus={(e) => {
                      // On mobile, prevent page scroll when textarea is focused
                      if (window.innerWidth < 768) {
                        setTimeout(() => {
                          e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }, 300);
                      }
                    }}
                  />
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                    <p className="text-xs text-muted-foreground hidden sm:block">
                      Press Ctrl+Enter to submit
                    </p>
                    <Button
                      onClick={handleSubmitAnswer}
                      disabled={isSubmitting || !isConnected || (!currentAnswer.trim() && !codeAnswer.trim())}
                      size="sm"
                      className="w-full sm:w-auto"
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Submitting...
                        </>
                      ) : (
                        'Submit Answer'
                      )}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="w-full text-center text-sm text-muted-foreground bg-muted p-2 rounded-lg">
                  {isConnecting ? 'Connecting to interview...' : isConnected ? 'Waiting for question...' : 'Disconnected'}
                </div>
              )}
            </div>
        </div>

      </div>
    </div>
  );
};

export default InterviewInterface;