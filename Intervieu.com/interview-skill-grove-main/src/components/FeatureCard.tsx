
import React from 'react';
import { LucideIcon } from 'lucide-react';

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon: Icon, title, description }) => {
  return (
    <div className="glass-card hover-lift group">
      <div className="flex flex-col items-start">
        <div className="p-3 rounded-xl bg-primary/10 text-primary mb-4 transition-transform group-hover:scale-110">
          <Icon size={24} />
        </div>
        <h3 className="text-xl font-medium mb-2">{title}</h3>
        <p className="text-foreground/70">{description}</p>
      </div>
    </div>
  );
};

export default FeatureCard;
