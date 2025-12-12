import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SessionProgress } from './SessionProgress';
import type { FoldersResponse } from '../types';

describe('SessionProgress', () => {
  const mockFolders: FoldersResponse = { root: '/music', folders: ['2025', '2024', '2023'] };

  it('renders with priorityPath and shows folder name as dropdown button', () => {
    render(<SessionProgress completed={5} priorityPath="/path/to/folder" folders={mockFolders} />);

    expect(screen.getByText('folder')).toBeInTheDocument();
    expect(screen.getByText('+5')).toBeInTheDocument();
  });

  it('renders without priorityPath and defaults to 2025', () => {
    render(<SessionProgress completed={10} folders={mockFolders} />);

    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('+10')).toBeInTheDocument();
  });

  it('extracts folder name from complex path', () => {
    render(<SessionProgress completed={3} priorityPath="/very/long/path/with/many/folders/music" folders={mockFolders} />);

    expect(screen.getByText('music')).toBeInTheDocument();
    expect(screen.getByText('+3')).toBeInTheDocument();
  });

  it('handles path with trailing slash', () => {
    render(<SessionProgress completed={7} priorityPath="/path/to/folder/" folders={mockFolders} />);

    expect(screen.getByText('folder')).toBeInTheDocument();
    expect(screen.getByText('+7')).toBeInTheDocument();
  });

  it('handles root path and defaults to 2025', () => {
    render(<SessionProgress completed={1} priorityPath="/" folders={mockFolders} />);

    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('opens dropdown when clicked and shows folder options', () => {
    render(<SessionProgress completed={5} folders={mockFolders} />);

    const dropdownButton = screen.getByText('2025');
    fireEvent.click(dropdownButton);

    expect(screen.getByText('2024')).toBeInTheDocument();
    expect(screen.getByText('2023')).toBeInTheDocument();
  });

  it('calls onPriorityChange when folder is selected', () => {
    const mockOnPriorityChange = vi.fn();

    render(<SessionProgress completed={5} onPriorityChange={mockOnPriorityChange} folders={mockFolders} />);

    const dropdownButton = screen.getByText('2025');
    fireEvent.click(dropdownButton);

    const folderOption = screen.getByText('2024');
    fireEvent.click(folderOption);

    expect(mockOnPriorityChange).toHaveBeenCalledWith('/music/2024');
  });

  it('calls onPriorityChange with null when 2025 is selected', () => {
    const mockOnPriorityChange = vi.fn();

    render(<SessionProgress completed={5} priorityPath="/music/2024" onPriorityChange={mockOnPriorityChange} folders={mockFolders} />);

    const dropdownButton = screen.getByText('2024');
    fireEvent.click(dropdownButton);

    const folderOption = screen.getByText('2025');
    fireEvent.click(folderOption);

    expect(mockOnPriorityChange).toHaveBeenCalledWith(null);
  });

  it('closes dropdown when clicking outside', () => {
    render(<SessionProgress completed={5} folders={mockFolders} />);

    const dropdownButton = screen.getByText('2025');
    fireEvent.click(dropdownButton);

    expect(screen.getByText('2024')).toBeInTheDocument();

    // Click outside (simulate mousedown on document)
    fireEvent(document, new MouseEvent('mousedown', { bubbles: true }));

    expect(screen.queryByText('2024')).not.toBeInTheDocument();
  });

  it('handles empty folders gracefully', () => {
    render(<SessionProgress completed={5} folders={{ root: '/music', folders: [] }} />);

    expect(screen.getByText('All')).toBeInTheDocument();
    expect(screen.getByText('+5')).toBeInTheDocument();
  });

  it('defaults to All when 2025 not in folders', () => {
    const foldersWithout2025: FoldersResponse = { root: '/music', folders: ['2024', '2023'] };

    render(<SessionProgress completed={5} folders={foldersWithout2025} />);

    expect(screen.getByText('All')).toBeInTheDocument();
  });
});
