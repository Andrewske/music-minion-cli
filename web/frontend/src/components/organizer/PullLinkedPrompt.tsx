import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';

/** What the prompt needs after a link call returned pullable tracks. */
export interface PullPrompt {
  bucketId: string;
  bucketName: string;
  playlistName: string;
  count: number;
}

interface PullLinkedPromptProps {
  prompt: PullPrompt | null;
  isPulling: boolean;
  onAssign: (prompt: PullPrompt) => void;
  onDismiss: () => void;
}

const trackWord = (count: number): string => (count === 1 ? 'track' : 'tracks');

export function PullLinkedPrompt({ prompt, isPulling, onAssign, onDismiss }: PullLinkedPromptProps): JSX.Element {
  return (
    <AlertDialog open={prompt !== null} onOpenChange={(open) => !open && onDismiss()}>
      <AlertDialogContent className="bg-obsidian-surface! border-obsidian-border!">
        {prompt && (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>Assign linked tracks?</AlertDialogTitle>
              <AlertDialogDescription className="text-white/60!">
                {prompt.count} {trackWord(prompt.count)} from <span className="text-white/90">{prompt.playlistName}</span>{' '}
                {prompt.count === 1 ? 'is' : 'are'} already in this playlist. Assign{' '}
                {prompt.count === 1 ? 'it' : 'them'} to <span className="text-white/90">{prompt.bucketName}</span>?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="bg-transparent! text-white/60 hover:bg-white/5! hover:text-white">
                Keep unassigned
              </AlertDialogCancel>
              <AlertDialogAction
                disabled={isPulling}
                onClick={() => onAssign(prompt)}
                className="bg-obsidian-accent/20 text-obsidian-accent hover:bg-obsidian-accent/30 disabled:opacity-50"
              >
                Assign {prompt.count}
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
