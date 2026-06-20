import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AwakeningProvider } from "@/components/layout/awakening-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "PNIXPG",
    template: "%s | PNIXPG",
  },
  description: "PNIXPG — AI study assistant, school search, focus timer and community",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body
        className="h-full flex flex-col overflow-hidden"
        suppressHydrationWarning
      >
        <AwakeningProvider>{children}</AwakeningProvider>
      </body>
    </html>
  );
}
