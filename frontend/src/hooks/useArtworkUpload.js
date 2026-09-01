import { useCallback, useEffect, useRef, useState } from "react";

import { artworkUrl } from "../config";

/**
 * File selection and preview for the three artwork upload dialogs.
 *
 * Object URLs are revoked when they are replaced and on unmount. The previous
 * implementation called `URL.createObjectURL` in three places and `revokeObjectURL`
 * nowhere, so every image previewed leaked a blob for the lifetime of the tab.
 */
export function useArtworkUpload() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const objectUrlRef = useRef(null);

  const releaseObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  useEffect(() => releaseObjectUrl, [releaseObjectUrl]);

  /** Show the artwork already stored for this entity, if any. */
  const setExistingArtwork = useCallback(
    (path) => {
      releaseObjectUrl();
      setFile(null);
      setPreviewUrl(path ? artworkUrl(path) : "");
    },
    [releaseObjectUrl],
  );

  const selectFile = useCallback(
    (event) => {
      const selected = event.target.files?.[0];

      if (!selected) {
        return;
      }

      releaseObjectUrl();

      const url = URL.createObjectURL(selected);
      objectUrlRef.current = url;

      setFile(selected);
      setPreviewUrl(url);
    },
    [releaseObjectUrl],
  );

  const reset = useCallback(() => {
    releaseObjectUrl();
    setFile(null);
    setPreviewUrl("");
  }, [releaseObjectUrl]);

  return { file, previewUrl, selectFile, setExistingArtwork, reset };
}
