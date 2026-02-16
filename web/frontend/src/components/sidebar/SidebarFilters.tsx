import { SidebarSection } from './SidebarSection';
import { FilterSidebar } from '../playlist-builder/FilterSidebar';

interface SidebarFiltersProps {
  sidebarExpanded: boolean;
}

export function SidebarFilters({ sidebarExpanded }: SidebarFiltersProps): JSX.Element {
  return (
    <SidebarSection title="Filters" sidebarExpanded={sidebarExpanded} defaultExpanded={false}>
      <FilterSidebar />
    </SidebarSection>
  );
}
