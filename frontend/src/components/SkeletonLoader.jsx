import React from "react";

export default function SkeletonLoader({ type = "hero" }) {
  if (type === "hero") {
    return (
      <div className="skeleton-hero-card">
        <div className="skeleton-gauge pulse" />
        <div className="skeleton-text-group">
          <div className="skeleton-title pulse" />
          <div className="skeleton-sub pulse" />
          <div className="skeleton-sub pulse short" />
        </div>
      </div>
    );
  }

  if (type === "cards") {
    return (
      <div className="skeleton-cards-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton-card pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="skeleton-generic pulse">
      <div className="skeleton-line pulse" />
      <div className="skeleton-line pulse" />
      <div className="skeleton-line pulse short" />
    </div>
  );
}
