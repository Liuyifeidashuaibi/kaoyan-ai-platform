"use client";

import Lightbox from "yet-another-react-lightbox";
import Zoom from "yet-another-react-lightbox/plugins/zoom";
import Thumbnails from "yet-another-react-lightbox/plugins/thumbnails";
import Fullscreen from "yet-another-react-lightbox/plugins/fullscreen";
import "yet-another-react-lightbox/styles.css";
import "yet-another-react-lightbox/plugins/thumbnails.css";

import { resolveUploadUrl } from "@/lib/config/api";

type SlideItem = {
  src: string;
  title: string;
  description?: string;
};

type ImageViewerProps = {
  open: boolean;
  index: number;
  slides: SlideItem[];
  onClose: () => void;
};

export function ImageViewer({ open, index, slides, onClose }: ImageViewerProps) {
  return (
    <Lightbox
      open={open}
      close={onClose}
      index={index}
      slides={slides}
      plugins={[Zoom, Thumbnails, Fullscreen]}
      zoom={{
        maxZoomPixelRatio: 4,
        zoomInMultiplier: 1.5,
        doubleTapDelay: 300,
        doubleClickDelay: 300,
        keyboardMoveDistance: 50,
        wheelZoomDistanceFactor: 100,
        pinchZoomDistanceFactor: 100,
        scrollToZoom: true,
      }}
      thumbnails={{
        position: "bottom",
        width: 60,
        height: 45,
        border: 2,
        borderRadius: 6,
        gap: 6,
        padding: 4,
        showToggle: false,
      }}
      styles={{
        container: { backgroundColor: "rgba(0,0,0,0.88)" },
      }}
      render={{
        /* bottom caption */
        slideFooter({ slide }) {
          const s = slide as SlideItem;
          if (!s.title && !s.description) return null;
          return (
            <div className="absolute bottom-14 left-0 right-0 flex flex-col items-center gap-0.5 px-4 text-center">
              {s.title && (
                <p className="text-sm font-semibold text-white/90">{s.title}</p>
              )}
              {s.description && (
                <p className="text-xs text-white/60">{s.description}</p>
              )}
            </div>
          );
        },
      }}
    />
  );
}

/** Build slide list from wrong-question list */
export function buildSlides(
  questions: Array<{
    image_path: string;
    title: string;
    category_name: string;
    created_at: string;
  }>
): SlideItem[] {
  return questions.map((q) => ({
    src: resolveUploadUrl(q.image_path),
    title: q.title,
    description: `${q.category_name} · ${new Date(q.created_at).toLocaleDateString("zh-CN")}`,
  }));
}
