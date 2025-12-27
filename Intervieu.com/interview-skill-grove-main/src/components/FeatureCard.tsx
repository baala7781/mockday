
import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  soon?: boolean;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon: Icon, title, description, soon = false }) => {
  return (
    <div className="glass-card hover-lift group h-full flex flex-col">
      <div className="flex flex-col items-start flex-1">
        <div className="flex items-center justify-between w-full mb-4">
          <div className="p-3 rounded-xl bg-primary/10 text-primary transition-transform group-hover:scale-110">
            <Icon size={24} />
          </div>
          {soon && (
            <Badge variant="secondary" className="ml-auto">
              Soon
            </Badge>
          )}
        </div>
        <h3 className="text-xl font-medium mb-2">{title}</h3>
        <p className="text-foreground/70 flex-1">{description}</p>
      </div>
    </div>
  );
};

export default FeatureCard;
