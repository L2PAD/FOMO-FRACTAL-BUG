import React from 'react';

const TerminalSection = ({ title, children, className = '' }) => {
  return (
    <div className={`bg-[#0F141A] rounded-lg p-4 ${className}`}>
      {title && (
        <div className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">
          {title}
        </div>
      )}
      <div className="space-y-3">
        {children}
      </div>
    </div>
  );
};

export default TerminalSection;
