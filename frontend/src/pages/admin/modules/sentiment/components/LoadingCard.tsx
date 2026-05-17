import React from "react";
import Card from "./Card";

interface LoadingCardProps {
  title: string;
}

export default function LoadingCard({ title }: LoadingCardProps) {
  return (
    <Card title={title}>
      <div className="flex items-center gap-3 text-slate-500">
        <div className="w-4 h-4 border-2 border-gray-200 border-t-gray-500 rounded-full animate-spin" />
        <span>Loading…</span>
      </div>
    </Card>
  );
}
