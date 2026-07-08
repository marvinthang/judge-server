import uuid
import subprocess

from dmoj.cptbox.utils import MemoryIO
from dmoj.error import InternalError, OutputLimitExceeded
from dmoj.executors import executors
from dmoj.executors.base_executor import BaseExecutor
from dmoj.graders.standard import StandardGrader
from dmoj.problem import TestCase
from dmoj.utils.unicode import utf8bytes
from dmoj.result import CheckerResult, Result

class TwoPhaseSignatureGrader(StandardGrader):
    def grade(self, case: TestCase) -> Result:
        result = Result(case)

        input_file = case.input_data_io()

        phase1_result = self._run_phase(case, self.phase1_binary, input_file)

        if phase1_result.result_flag:
            case.free_data()
            return phase1_result

        phase2_input = MemoryIO()
        original_input = input_file.to_bytes()
        phase2_input.write(original_input)
        if original_input and not original_input.endswith(b'\n'):
            phase2_input.write(b'\n')
        phase2_input.write(phase1_result.proc_output)
        phase2_input.seal()

        phase2_result = self._run_phase(case, self.phase2_binary, phase2_input)

        if phase2_result.result_flag:
            case.free_data()
            return phase2_result

        self._merge_phase_results(result, phase1_result, phase2_result)
        check = self.check_result(case, result)

        # checkers must either return a boolean (True: full points, False: 0 points)
        # or a CheckerResult, so convert to CheckerResult if it returned bool
        if not isinstance(check, CheckerResult):
            check = CheckerResult(check, case.points if check else 0.0)

        result.result_flag |= [Result.WA, Result.AC][check.passed]
        result.points = check.points
        result.feedback = check.feedback or result.feedback
        result.extended_feedback = check.extended_feedback or result.extended_feedback

        case.free_data()

        return result

    def _run_phase(self, case: TestCase, binary: BaseExecutor, input_file) -> Result:
        result = Result(case)
        process = binary.launch(
            time=self.problem.time_limit,
            memory=self.problem.memory_limit,
            file_io=case.config.file_io,
            symlinks=case.config.symlinks,
            stdin=input_file or subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            wall_time=case.config.wall_time_factor * self.problem.time_limit,
        )

        self._current_proc = process

        assert process is not None
        try:
            result.proc_output, error = process.communicate(
                None, outlimit=case.config.output_limit_length, errlimit=1048576
            )
        except OutputLimitExceeded:
            error = b''
            process.kill()
        finally:
            process.wait()
            self._current_proc = None

        binary.populate_result(error, result, process)

        return result

    def _merge_phase_results(self, result, phase1_result, phase2_result) -> Result:
        result.execution_time = phase1_result.execution_time + phase2_result.execution_time
        result.wall_clock_time = max(phase1_result.wall_clock_time, phase2_result.wall_clock_time)
        result.max_memory = max(phase1_result.max_memory, phase2_result.max_memory)
        result.context_switches = (
            phase1_result.context_switches[0] + phase2_result.context_switches[0],
            phase1_result.context_switches[1] + phase2_result.context_switches[1],
        )
        result.result_flag = phase1_result.result_flag | phase2_result.result_flag
        result.proc_output = phase2_result.proc_output
        result.feedback = phase2_result.feedback or phase1_result.feedback
        result.extended_feedback = phase2_result.extended_feedback or phase1_result.extended_feedback

    def _generate_phase_binary(self, handler_data, phase_name) -> BaseExecutor:
        executor = executors[self.language].Executor
        is_signature_gradable = getattr(executor, 'is_signature_gradable', False)
        ext = getattr(executor, 'ext', None)

        if is_signature_gradable and ext in ('c', 'cpp'):
            aux_sources = {}

            entry_point = self.problem.problem_data[handler_data['entry']]
            header = self.problem.problem_data[handler_data['header']]

            submission_prefix = f'#include "{handler_data["header"]}"\n'
            if not handler_data.get('allow_main', False):
                submission_prefix += '#define main main_%s\n' % uuid.uuid4().hex

            aux_sources[self.problem.id + '_submission'] = utf8bytes(submission_prefix) + self.source

            aux_sources[handler_data['header']] = header
            entry = entry_point
            return executor(
                self.problem.id,
                entry,
                storage_namespace=self.problem.storage_namespace,
                aux_sources=aux_sources,
                defines=['-DSIGNATURE_GRADER', f'-D{phase_name}'],
            )
        else:
            raise InternalError('no valid runtime for signature grading %s found' % self.language)


    def _generate_binary(self):
        config = self.problem.config['two_phase_signature_grader']

        self.phase1_binary = self._generate_phase_binary(config['phase1'], 'SIGNATURE_PHASE_1')
        self.phase2_binary = self._generate_phase_binary(config['phase2'], 'SIGNATURE_PHASE_2')

        return self.phase2_binary
