import React from "react";
import { ReliabilityLevel } from "../types/sentimentAdmin.types";

const levelStyles: Record<ReliabilityLevel, string> = {
  OK: "text-emerald-600",
  WARN: "text-amber-600",
  DEGRADED: "text-orange-600",
  CRITICAL: "text-red-600",
  UNKNOWN: "text-slate-500",
};

interface StatusBadgeProps {
  level: ReliabilityLevel;
  size?: "sm" | "md" | "lg";
}

export default function StatusBadge({ level, size = "md" }: StatusBadgeProps) {
  const color = levelStyles[level] ?? levelStyles.UNKNOWN;
  
  const sizeClasses = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  };

  return (
    <span className={`font-semibold ${color} ${sizeClasses[size]}`}>
      {level}
    </span>
  );
}
