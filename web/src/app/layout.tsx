import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ServiceWorkerRegister } from "@/components/pwa/service-worker-register";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dajung AI",
  description: "다정 운영진 지식관리·인수인계·예산 보조 AI",
  manifest: "/manifest.json",
};

// webapp-spec S7: theme_color/background_color duplicated here from
// manifest.json — Next 14+ moved theme-color out of `metadata` into this
// separate `viewport` export (browser install-prompt chrome reads this one).
// webapp-spec S7: manifest.json의 theme_color/background_color를 여기서도
// 반복 — Next 14+부터 theme-color가 `metadata`에서 이 별도 `viewport` export로
// 옮겨졌다(브라우저 설치 프롬프트 크롬이 이걸 읽는다).
export const viewport: Viewport = {
  themeColor: "#422A1E",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        <ServiceWorkerRegister />
        {children}
      </body>
    </html>
  );
}
