// components/ui/index.ts — Re-exports all UI primitives.
// Use: import { Button, IconButton, DropdownMenu } from '../components/ui';

export { Button, IconButton }                            from './Button';
export { DropdownMenu, DropdownTrigger }                 from './Dropdown';
export type { DropdownItem }                             from './Dropdown';
export { TabStrip }                                      from './FileTab';
export type { FileTab }                                  from './FileTab';
export { EmptyState }                                    from './EmptyState';