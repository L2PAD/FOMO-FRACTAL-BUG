import React from "react";

interface CardProps {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}

export default function Card({ title, children, right, className = "" }: CardProps) {
  return (
    <div
      className={`
        rounded-xl p-4 
        bg-white
        ${className}
      `}
    >
      <div className="flex items-center gap-3 mb-3">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </div>
  );
}
