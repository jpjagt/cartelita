/** The `gridcheckchange` event's detail (ui/GridCheckButtons.astro): the
    group's checked values in option order, and the option just toggled. */
export interface GridCheckChange {
  values: string[];
  value: string;
  checked: boolean;
}
