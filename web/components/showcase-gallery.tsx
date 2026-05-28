'use client';

import { CommunityGallery } from '@/components/community-gallery';

/** Homepage showcase section (official + community videos). */
export function ShowcaseGallery() {
  return <CommunityGallery showHeader compact={false} />;
}
