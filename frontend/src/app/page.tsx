import { HomeTemplate } from "@/components/templates/HomeTemplate";
import { JobList } from "@/components/organisms/JobList";
import { NewConversionForm } from "@/components/organisms/NewConversionForm";

export default function HomePage() {
  return <HomeTemplate conversionForm={<NewConversionForm />} jobList={<JobList />} />;
}
