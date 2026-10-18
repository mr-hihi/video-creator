import type { Metadata } from "next";
import { FilmAnalysisHistory } from "@/components/organisms/FilmAnalysisHistory";
import { NewFilmAnalysisForm } from "@/components/organisms/NewFilmAnalysisForm";
import { FilmAnalysisTemplate } from "@/components/templates/FilmAnalysisTemplate";

export const metadata: Metadata = {
  title: "Film Analysis",
};

export default function FilmAnalysisPage() {
  return <FilmAnalysisTemplate analysisForm={<NewFilmAnalysisForm />} analysisHistory={<FilmAnalysisHistory />} />;
}
