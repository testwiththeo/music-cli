declare module "yt-search" {
  const ytSearch: (query: string) => Promise<{
    videos: Array<{
      title: string;
      videoId: string;
      url: string;
      timestamp?: string;
      duration: { timestamp: string };
      author: { name: string };
    }>;
  }>;
  export default ytSearch;
}
