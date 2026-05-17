import React from "react";
import Card from "./Card";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorCardProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorCard({ title, message, onRetry }: ErrorCardProps) {
  return (
    <Card
      title={title}
      className="bg-red-50/70"
      right={
        onRetry ? (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg
              bg-gray-50 hover:bg-gray-100 
              text-slate-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Повторить
          </button>
        ) : null
      }
    >
      <div className="flex items-start gap-3 text-red-700">
        <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
        <p className="text-sm whitespace-pre-wrap">{message}</p>
      </div>
    </Card>
  );
}
