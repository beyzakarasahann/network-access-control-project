import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NAC Monitoring",
  description: "S3M Staj — Network Access Control izleme paneli",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
