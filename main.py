"""
Runs all modules
"""

from Raw_Data_Crawling.github.run import main as run_module1
from Vulnerability_Untangling_Module.run import main as run_module2
from Multi_granularity_Dependency_Extraction_Module.run import main as run_module3
from Trace_based_Filtering_Module.github.window import main as run_module4

def main(Years=['2016'], Months=['8']):
    run_module1(Years, Months)
    run_module2(Years, Months)
    run_module3(Years, Months)
    run_module4(Years, Months)

if __name__ == '__main__':
    #Run modules on all years and months
    #Years = [str(year) for year in range(2001, 2024)]
    #Months = [str(month) for month in range(1, 13)]
    main()
