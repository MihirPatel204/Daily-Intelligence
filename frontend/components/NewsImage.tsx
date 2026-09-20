"use client";

import React, { useState } from "react";

interface NewsImageProps {
  src?: string | null;
  alt?: string;
  credit?: string;
  caption?: string;
  aspectRatio?: "video" | "wide" | "square" | "thumbnail" | "auto";
  className?: string;
  containerClassName?: string;
}

export default function NewsImage({
  src,
  alt = "News dispatch photograph",
  credit,
  caption,
  aspectRatio = "video",
  className = "",
  containerClassName = "",
}: NewsImageProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // If no source or error occurred, show nothing at all (clean newspaper text format)
  if (!src || hasError) {
    return null;
  }

  const aspectClass =
    aspectRatio === "wide"
      ? "aspect-[16/9] sm:aspect-[21/9]"
      : aspectRatio === "video"
      ? "aspect-[16/9]"
      : aspectRatio === "square"
      ? "aspect-square"
      : aspectRatio === "thumbnail"
      ? "w-14 h-14 md:w-16 md:h-16 flex-shrink-0"
      : "";

  return (
    <figure className={`relative overflow-hidden group/img bg-[var(--background-alt)] border border-[var(--border-light)] ${aspectClass} ${containerClassName}`}>
      {/* Subtle skeleton shimmer while image loads */}
      {!isLoaded && (
        <div className="absolute inset-0 skeleton" />
      )}

      {/* Actual image */}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        onLoad={() => setIsLoaded(true)}
        onError={() => setHasError(true)}
        className={`
          w-full h-full object-cover transition-all duration-500 ease-out
          filter contrast-[1.02]
          group-hover/img:scale-[1.03]
          ${isLoaded ? "opacity-100" : "opacity-0"}
          ${className}
        `}
      />

      {/* Credit badge if available (newspaper dispatch attribution) */}
      {credit && isLoaded && (
        <div className="absolute bottom-1 right-1.5 pointer-events-none">
          <span className="bg-black/60 backdrop-blur-[2px] text-white/90 text-[8px] font-sans font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-[2px]">
            {credit}
          </span>
        </div>
      )}

      {/* Optional Editorial Caption */}
      {caption && isLoaded && (
        <figcaption className="sr-only">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
