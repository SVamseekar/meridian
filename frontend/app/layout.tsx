import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Meridian Settings",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <nav style={{ padding: "1rem", borderBottom: "1px solid #ddd" }}>
          <strong>Meridian</strong>
          <span style={{ marginLeft: "1.5rem" }}>
            <a href="/settings/write-keys">Write Keys</a>
          </span>
        </nav>
        <main style={{ padding: "1.5rem" }}>{children}</main>
      </body>
    </html>
  );
}
