"use client";

import ReactMarkdown, { defaultUrlTransform, type Components, type UrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { MarkdownImage } from "@/components/atoms/MarkdownImage";
import { MarkdownLink } from "@/components/atoms/MarkdownLink";
import { resolveJobImageUrl } from "@/features/jobs/utils";

const REMARK_PLUGINS = [remarkGfm];

const MARKDOWN_COMPONENTS: Components = {
  img: MarkdownImage,
  a: MarkdownLink,
};

interface MarkdownPreviewProps {
  jobId: string;
  markdown: string;
}

export function MarkdownPreview({ jobId, markdown }: MarkdownPreviewProps) {
  const transformUrl: UrlTransform = (url, key, node) => {
    const safeUrl = defaultUrlTransform(url);
    const isImageSource = node.tagName === "img" && key === "src";
    if (!isImageSource || !safeUrl) return safeUrl;
    return resolveJobImageUrl(jobId, safeUrl);
  };

  return (
    <article className="markdown-preview">
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={MARKDOWN_COMPONENTS} urlTransform={transformUrl}>
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
