import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "ImpactLab",
  description: "DID + 時系列反実仮想をブラウザで試せるデモ"
};

type Props = {
  children: ReactNode;
};

export default function RootLayout({ children }: Props) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
