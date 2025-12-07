
import React from 'react';
import Hero from '../components/Hero';
import FeatureCard from '../components/FeatureCard';
import { Brain, Clock, Check, Shield, BarChart, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const features = [
  {
    icon: Brain,
    title: 'AI-Driven Interviews',
    description: 'Advanced algorithms adapt questions based on your responses for a personalized experience.'
  },
  {
    icon: Clock,
    title: 'Real-Time Feedback',
    description: 'Receive immediate insights on your performance during the interview process.'
  },
  {
    icon: Check,
    title: 'Objective Evaluation',
    description: 'Unbiased assessment of your technical and soft skills without human judgment.'
  },
  {
    icon: Shield,
    title: 'Malpractice Detection',
    description: 'Sophisticated monitoring to ensure interview integrity and fairness.'
  },
  {
    icon: BarChart,
    title: 'Comprehensive Reports',
    description: 'Detailed performance analytics with actionable improvement suggestions.'
  },
  {
    icon: Users,
    title: 'Practice Community',
    description: 'Connect with peers to share experiences and preparation strategies.'
  }
];

const Index: React.FC = () => {
  return (
    <div className="page-transition">
      <Hero />
      
      {/* Features Section */}
      <section className="section bg-muted/30">
        <div className="page-container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl font-medium mb-4">Designed for Excellence</h2>
            <p className="text-foreground/70">
              Our platform combines cutting-edge AI with thoughtful design to create
              the most effective interview preparation experience.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <div 
                key={feature.title}
                className="animate-in slide-in-from-bottom duration-300"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <FeatureCard 
                  icon={feature.icon} 
                  title={feature.title} 
                  description={feature.description} 
                />
              </div>
            ))}
          </div>
        </div>
      </section>
      
      {/* CTA Section */}
      <section className="section relative overflow-hidden">
        <div className="absolute top-1/2 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10 -translate-y-1/2"></div>
        <div className="absolute top-1/2 left-0 w-72 h-72 bg-accent/10 rounded-full blur-3xl -z-10 -translate-y-1/2"></div>
        
        <div className="page-container">
          <Card className="max-w-4xl mx-auto">
            <CardContent className="p-10 md:p-16">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-medium mb-4">Ready to Transform Your Interview Skills?</h2>
              <p className="text-foreground/70 max-w-2xl mx-auto">
                Join thousands of candidates who have improved their interview performance and landed their dream jobs.
              </p>
            </div>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button asChild className="w-full sm:w-auto">
                <Link to="/start-interview">Start Practicing Now</Link>
              </Button>
              <Button variant="outline" asChild className="w-full sm:w-auto">
                <Link to="/dashboard">View Dashboard</Link>
              </Button>
            </div>
            </CardContent>
          </Card>
        </div>
      </section>
      
      {/* Footer */}
      <footer className="py-10 border-t">
        <div className="page-container">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center space-x-2">
              <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-sm">I</span>
              </div>
              <span className="font-semibold text-lg">MockDay</span>
            </div>
            
            <div className="flex items-center gap-4 text-sm text-foreground/70">
              <a href="#" className="hover:text-primary transition-colors">Privacy</a>
              <a href="#" className="hover:text-primary transition-colors">Terms</a>
              <a href="#" className="hover:text-primary transition-colors">Contact</a>
            </div>
            
            <p className="text-sm text-foreground/70">
              © {new Date().getFullYear()} MockDay. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
