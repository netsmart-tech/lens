"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { JiraComment } from "@/lib/types";

interface CommentComposerProps {
  tenant: string;
  issueKey: string;
  onCommentAdded: (comment: JiraComment) => void;
}

const MIN_ROWS = 3;
const MAX_ROWS = 12;
// Line height in pixels matching Tailwind text-sm leading. Empirically tuned
// for the default Textarea styles (py-2, text-sm = 14px ~ 20px line-height).
const LINE_HEIGHT_PX = 20;
const VERTICAL_PADDING_PX = 16; // py-2 top + bottom

export function CommentComposer({
  tenant,
  issueKey,
  onCommentAdded,
}: CommentComposerProps) {
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoGrow = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const minHeight = MIN_ROWS * LINE_HEIGHT_PX + VERTICAL_PADDING_PX;
    const maxHeight = MAX_ROWS * LINE_HEIGHT_PX + VERTICAL_PADDING_PX;
    const next = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    autoGrow();
  }, [body, autoGrow]);

  const trimmed = body.trim();
  const disabled = submitting || trimmed.length === 0;

  const submit = useCallback(async () => {
    if (trimmed.length === 0 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const comment = await api.postComment(tenant, issueKey, trimmed);
      onCommentAdded(comment);
      setBody("");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to post comment",
      );
    } finally {
      setSubmitting(false);
    }
  }, [trimmed, submitting, tenant, issueKey, onCommentAdded]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void submit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setBody("");
      setError(null);
    }
  };

  return (
    <div className="space-y-2">
      <label htmlFor="comment-composer" className="sr-only">
        Write a comment
      </label>
      <Textarea
        id="comment-composer"
        ref={textareaRef}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Write a comment…"
        rows={MIN_ROWS}
        disabled={submitting}
        aria-label="Write a comment"
        className="resize-none"
      />
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          <kbd className="rounded border bg-muted px-1 py-0.5 text-[10px] font-medium">
            {typeof navigator !== "undefined" &&
            navigator.platform.toLowerCase().includes("mac")
              ? "⌘"
              : "Ctrl"}
            +Enter
          </kbd>{" "}
          to submit ·{" "}
          <kbd className="rounded border bg-muted px-1 py-0.5 text-[10px] font-medium">
            Esc
          </kbd>{" "}
          to clear
        </p>
        <Button
          type="button"
          size="sm"
          onClick={submit}
          disabled={disabled}
          aria-disabled={disabled}
        >
          {submitting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Posting…
            </>
          ) : (
            <>
              <Send className="h-3.5 w-3.5" />
              Comment
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
