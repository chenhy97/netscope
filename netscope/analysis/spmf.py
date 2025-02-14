"""
Python 3 Wrapper for SPMF
http://www.philippe-fournier-viger.com/spmf

Inspiration from:
https://github.com/fandu/maximal-sequential-patterns-mining
http://forum.ai-directory.com/read.php?5,5510
"""

__author__ = "Lorenz Leitner"
__version__ = "1.4"
__license__ = "GNU GPL v3.0"

from typing import Iterator
import pandas as pd
import os
import subprocess
import tempfile


class Spmf:
    def __init__(self,
                 algorithm_name,
                 input_direct=None,
                 input_type="normal",
                 input_filename="",
                 output_filename="spmf-output.txt",
                 arguments=[],
                 spmf_bin_location_dir=".",
                 memory=0,
                 echo=False):
        self.executable_dir_ = spmf_bin_location_dir
        self.executable_ = "spmf.jar"

        self.is_exist_executable_ = os.path.isfile(
            os.path.join(self.executable_dir_, self.executable_))

        if not self.is_exist_executable_:
            self.executable_dir_ = os.path.dirname(os.path.realpath(__file__))
            self.is_exist_executable_ = os.path.isfile(
                os.path.join(self.executable_dir_, self.executable_))

        if not self.is_exist_executable_:
            raise FileNotFoundError(self.executable_ + " not found. Please" +
                                    " use the spmf_bin_location_dir argument.")

        self.agorithm_name_ = algorithm_name
        self.input_ = self.handle_input(
            input_direct, input_filename, input_type)
        self.output_ = output_filename
        self.arguments_ = [str(a) for a in arguments]
        self.patterns_ = []
        self.df_ = None
        self.memory_ = memory
        self.echo_ = echo

    def handle_input(self, input_direct, input_filename, input_type):
        if input_filename:
            return input_filename
        if type(input_direct) == str:
            if input_type == "normal":
                file_ending = ".txt"
            elif input_type == "text":
                file_ending = ".text"
            return self.write_temp_input_file(input_direct,
                                              file_ending)
        if type(input_direct) == list:
            if input_type == "normal":
                seq_spmf = ""
                for seq in input_direct:
                    for item_set in seq:
                        for item in item_set:
                            seq_spmf += str(item) + ' '
                        seq_spmf += str(-1) + ' '
                    seq_spmf += str(-2) + '\n'
                return self.write_temp_input_file(seq_spmf, ".txt")
            if input_type == "text":
                seq_str = ""
                for seq in input_direct:
                    seq_str += seq + ". "
                return self.write_temp_input_file(seq_str, ".text")
        raise TypeError("no correct input format found (required: " +
                        "list or str, or input file via" +
                        " input_filename parameter)")

    def write_temp_input_file(self, input_text, file_ending):
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.write(bytes(input_text, 'UTF-8'))
        name = tf.name
        os.rename(name, name + file_ending)
        return name + file_ending

    def run(self):
        """
        Start the SPMF process
        Calls the Java binary with the previously specified parameters
        """
        subprocess_arguments = ["java"]

        # http://www.philippe-fournier-viger.com/spmf/index.php?link=FAQ.php#memory
        if self.memory_:
            subprocess_arguments.append(f'-Xmx{self.memory_}m')

        subprocess_arguments.extend(
            ["-jar",
             os.path.join(self.executable_dir_, self.executable_),
             "run",
             self.agorithm_name_,
             self.input_, self.output_])
        subprocess_arguments.extend(self.arguments_)

        proc = subprocess.check_output(subprocess_arguments)
        proc_output = proc.decode()
        self.proc_output = proc_output
        if self.echo_:
            print(" ".join(subprocess_arguments))
            print(proc_output)
        if "java.lang.IllegalArgumentException" in proc_output:
            print(proc_output)
            raise TypeError("java.lang.IllegalArgumentException")

    def parse_output(self):
        """
        Parse the output of SPMF and saves in in member variable patterns_
        -1 separates itemsets
        -2 indicates end of a sequence
        http://data-mining.philippe-fournier-viger.com/introduction-to-sequential-rule-mining/#comment-4114
        """
        lines = []
        with open(self.output_, "r") as f:
            lines = f.readlines()

        patterns = []
        for line in lines:
            line = line.strip()
            patterns.append(line.split("#"))

        self.patterns_ = patterns
        return patterns

    def to_pandas_dataframe(self, pickle=False):
        """
        Convert output to pandas DataFrame
        pickle: Save as serialized pickle
        """
        # TODO: Optional parameter for pickle file name

        patterns_list, names = self.to_list()
        names.insert(0, 'pattern')
        df = pd.DataFrame([{name: pattern[i] for i, name in enumerate(names)}
                           for pattern in patterns_list])
        self.df_ = df

        if pickle:
            df.to_pickle(self.output_.replace(".txt", ".pkl"))
        return df

    def to_list(self):
        if not self.patterns_:
            self.parse_output()

        patterns_list = []
        for pattern_sup in self.patterns_:
            pattern = pattern_sup[0]
            if ' -1 ' in pattern:
                pattern = [p.split() for p in pattern.split(' -1 ')[:-1]]
            else:
                pattern = pattern.split()
            pattern_sup = pattern_sup[1:]

            sups = []
            for sup in pattern_sup:
                sup = sup.split()[1:]
                if len(sup) == 1:
                    sup = int(sup[0])
                else:
                    sup = [int(s) for s in sup]
                sups.append(sup)

            patterns_list.append([pattern]+sups)

        assert self.patterns_, "spmf output is empty"

        names = [sup.split()[0].strip(":").lower() for sup in pattern_sup]
        return patterns_list, names

    def to_csv(self, file_name, df=None, list_as_string=True):
        """
        Save output as csv
        Either use member variable if it has already been set,
        or re-set it using to_pandas_dataframe, or use given dataframe
        list_as_string: Fix CSV output so that '[]' is not present
        """
        if self.df_ is None and df is None:
            self.df_ = self.to_pandas_dataframe()

        if df is not None:
            self.df_ = df

        if not list_as_string:
            self.df_.to_csv(file_name, sep=';', index=False)
        else:
            df = self.df_
            for _, row in df.iterrows():
                row['pattern'] = ','.join(row['pattern'])

            df.to_csv(file_name, sep=';', index=False)


if __name__ == "__main__":
    # spmf = Spmf("FPGrowth_itemsets", input_filename="contextPasquier99.txt",
    #             output_filename="output.txt", arguments=[0.1])
    spmf = Spmf("PrefixSpan", input_filename="contextPrefixSpan.txt",
                output_filename="output.txt", arguments=['50%', 5, 'true'])
    spmf.run()
    L, names = spmf.to_list()
    print(names)
    for i in range(4):
        print(L[i])
    print(spmf.to_pandas_dataframe().head())
