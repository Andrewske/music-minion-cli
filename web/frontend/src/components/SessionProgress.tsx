
import { useState, useEffect, useRef } from 'react';
import type { FoldersResponse } from '../types';

interface SessionProgressProps {
  completed: number;
  priorityPath?: string;
  onPriorityChange?: (newPriorityPath: string | null) => void;
  folders?: FoldersResponse;
}

export function SessionProgress({ completed, priorityPath, onPriorityChange, folders: foldersData }: SessionProgressProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Use passed folders or default to empty array
  const folders = foldersData?.folders || [];

  // Default to "2025" when no priority is set and "2025" exists in folders
  const currentFolderName = priorityPath?.split('/').filter(Boolean).pop() ||
    (folders.includes('2025') ? '2025' : 'All');

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleFolderSelect = (folderName: string) => {
    const newPriorityPath = folderName === '2025' || folderName === 'All' ? null : `${foldersData?.root || '/music'}/${folderName}`;
    onPriorityChange?.(newPriorityPath);
    setIsOpen(false);
  };

  return (
    <div className="w-full">
      <div className="flex items-center gap-2">
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-emerald-400 font-mono truncate max-w-[200px] hover:text-emerald-300 transition-colors flex items-center gap-1"
            title={`Priority folder: ${currentFolderName}`}
          >
            {currentFolderName}
            <span className={`text-xs transition-transform ${isOpen ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>

          {isOpen && (
            <div className="absolute top-full left-0 mt-1 bg-slate-800 border border-slate-600 rounded-md shadow-lg z-10 min-w-[200px] max-h-48 overflow-y-auto">
              {folders.map((folder) => (
                <button
                  key={folder}
                  onClick={() => handleFolderSelect(folder)}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 transition-colors ${
                    folder === currentFolderName ? 'text-emerald-400 bg-slate-700' : 'text-slate-200'
                  }`}
                >
                  {folder}
                </button>
              ))}
            </div>
          )}
        </div>
        <span className="text-slate-200 font-bold">+{completed}</span>
      </div>
    </div>
  );
}
