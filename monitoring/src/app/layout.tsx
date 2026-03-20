import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NAC — Ağ erişim izleme",
  description: "Kullanıcı dostu NAC / RADIUS durum paneli",
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
