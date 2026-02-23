interface GenreTagProps {
  genre: {
    name: string;
    emoji_id?: string | null;
  };
  onClick?: () => void;
  className?: string;
}

export function GenreTag({ genre, onClick, className = '' }: GenreTagProps): JSX.Element {
  const content = (
    <>
      {genre.emoji_id && <span className="mr-1">{genre.emoji_id}</span>}
      <span>{genre.name}</span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center hover:text-white/80 transition-colors ${className}`}
      >
        {content}
      </button>
    );
  }

  return (
    <span className={`inline-flex items-center ${className}`}>
      {content}
    </span>
  );
}
