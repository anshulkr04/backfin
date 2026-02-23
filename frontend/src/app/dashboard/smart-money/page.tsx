"use client";

import { Users } from "lucide-react";

export default function SmartMoneyPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2 bg-white">
        <Users size={18} className="text-orange-500" />
        <h1 className="text-lg font-bold text-gray-900">Smart Money</h1>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
        <Users size={40} className="mb-4 text-gray-300" />
        <p className="text-sm font-medium text-gray-500">Coming Soon</p>
        <p className="text-xs text-gray-400 mt-1">
          Track institutional investors and smart money flows
        </p>
      </div>
    </div>
  );
}
