import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Monorepo / ust dizinde baska lockfile varken izolasyon
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
