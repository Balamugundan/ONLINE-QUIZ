import sys
import os
import uuid
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import app

class QuizSystemTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_e2e_quiz_lifecycle(self):
        # 1. Health check
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'online')
        print("[PASS] 1. Health Check Endpoint")

        # 2. Public settings
        res = self.client.get('/api/quiz/settings')
        self.assertEqual(res.status_code, 200)
        self.assertIn('quiz_title', res.json['data'])
        print("[PASS] 2. Public Quiz Settings")

        # 3. Admin Authentication
        res = self.client.post('/api/admin/login', json={'username': 'Admin', 'password': 'Admin@01'})
        self.assertEqual(res.status_code, 200)
        token = res.json['token']
        headers = {'Authorization': f'Bearer {token}'}
        print("[PASS] 3. Admin Login & Signed Token Generation")

        # 4. Admin Dashboard Stats
        res = self.client.get('/api/admin/dashboard', headers=headers)
        self.assertEqual(res.status_code, 200)
        print(f"[PASS] 4. Admin Dashboard Metrics: {res.json['data']['total_questions']} Questions")

        # 5. Question Management - Add
        res = self.client.post('/api/admin/questions', headers=headers, json={
            'question_text': 'What is Python Flask?',
            'options': {
                'A': 'A micro web framework',
                'B': 'A relational database',
                'C': 'A CSS styling library',
                'D': 'A browser rendering engine'
            },
            'correct_answer': 'A',
            'marks': 10,
            'time_limit': 45
        })
        self.assertEqual(res.status_code, 201)
        new_qid = res.json['data']['_id']
        print(f"[PASS] 5. Admin Add Question (ID: {new_qid})")

        # 6. Question Management - Edit
        res = self.client.put(f'/api/admin/questions/{new_qid}', headers=headers, json={
            'question_text': 'What is Python Flask framework?',
            'marks': 15
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['data']['marks'], 15)
        print("[PASS] 6. Admin Update Question")

        # 7. Student Login & Validation
        reg_no = f"REG_{uuid.uuid4().hex[:6].upper()}"
        res = self.client.post('/api/student/login', json={'name': 'Jane Doe', 'register_number': reg_no})
        self.assertEqual(res.status_code, 200)
        print("[PASS] 7. Student Entry & Validation")

        # 8. Start Quiz Attempt
        res = self.client.post('/api/quiz/start', json={'name': 'Jane Doe', 'register_number': reg_no})
        self.assertEqual(res.status_code, 200)
        attempt_id = res.json['attempt']['_id']
        questions = res.json['questions']
        
        # Verify student security: NO correct_answer in client payload!
        for q in questions:
            self.assertNotIn('correct_answer', q, "Security Alert: correct_answer leaked to frontend!")
        print(f"[PASS] 8. Quiz Start: Attempt Created (Security Verified: 0 answer leaks across {len(questions)} questions)")

        # 9. Autosave Answer
        res = self.client.post('/api/quiz/save-answer', json={
            'attempt_id': attempt_id,
            'question_id': new_qid,
            'selected_option': 'A'
        })
        self.assertEqual(res.status_code, 200)
        print("[PASS] 9. Real-time Answer Autosave")

        # 10. Submit Quiz & Backend Scoring
        res = self.client.post('/api/quiz/submit', json={'attempt_id': attempt_id})
        self.assertEqual(res.status_code, 200)
        summary = res.json['data']
        self.assertEqual(summary['correct_answers'], 1)
        self.assertEqual(summary['score'], 15)
        print(f"[PASS] 10. Server-side Quiz Evaluation: Score = {summary['score']}/{summary['total_marks']} ({summary['percentage']}%)")

        # 11. Student Result Query
        res = self.client.get(f'/api/quiz/result/{attempt_id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['data']['student_name'], 'Jane Doe')
        print("[PASS] 11. Student Result Summary Retrieval")

        # 12. Admin Individual Result Inspection
        res = self.client.get(f'/api/admin/results/{attempt_id}', headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.json['data']['detailed_results']) > 0)
        print("[PASS] 12. Admin Detailed Result Inspection with Question Breakdown")

        # 13. Prevent Duplicate Submission
        res = self.client.post('/api/student/login', json={'name': 'Jane Doe', 'register_number': reg_no})
        self.assertEqual(res.status_code, 409)
        print("[PASS] 13. Duplicate Submission Prevention (HTTP 409)")

        # 14. Student Anti-Cheating Activity Logging
        new_student_reg = f"MON_{uuid.uuid4().hex[:6].upper()}"
        res = self.client.post('/api/quiz/start', json={'name': 'Monitored Student', 'register_number': new_student_reg})
        self.assertEqual(res.status_code, 200)
        mon_attempt_id = res.json['attempt']['_id']
        mon_token = res.json['attempt']['session_token']

        # Log TAB_SWITCH event
        res = self.client.post('/api/quiz/activity-log', json={
            'attempt_id': mon_attempt_id,
            'event_type': 'TAB_SWITCH',
            'event_description': 'Switched to search engine tab',
            'event_count': 1
        })
        self.assertEqual(res.status_code, 200)

        # Log FULLSCREEN_EXIT event
        res = self.client.post('/api/quiz/activity-log', json={
            'attempt_id': mon_attempt_id,
            'event_type': 'FULLSCREEN_EXIT',
            'event_description': 'Exited fullscreen examination mode',
            'event_count': 2
        })
        self.assertEqual(res.status_code, 200)
        print("[PASS] 14. Anti-Cheat Activity Logging into MongoDB")

        # 15. Student Heartbeat Check
        res = self.client.post('/api/quiz/heartbeat', json={
            'attempt_id': mon_attempt_id,
            'session_token': mon_token
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['data']['status'], 'active')
        self.assertFalse(res.json['data']['is_terminated'])
        print("[PASS] 15. Student Live Heartbeat & Session Sync")

        # 16. Admin Live Student Monitoring
        res = self.client.get('/api/admin/live-monitoring', headers=headers)
        self.assertEqual(res.status_code, 200)
        monitoring_list = res.json['data']
        self.assertTrue(len(monitoring_list) > 0)
        mon_record = next((s for s in monitoring_list if s['_id'] == mon_attempt_id), None)
        self.assertIsNotNone(mon_record)
        self.assertEqual(mon_record['tab_switches_count'], 1)
        self.assertEqual(mon_record['fullscreen_exits_count'], 1)
        print(f"[PASS] 16. Admin Live Monitoring: Detected {len(monitoring_list)} Sessions with Live Anti-Cheat Counters")

        # 17. Admin Activity Logs Retrieval
        res = self.client.get(f'/api/admin/activity-logs/{mon_attempt_id}', headers=headers)
        self.assertEqual(res.status_code, 200)
        logs = res.json['data']
        self.assertEqual(len(logs), 2)
        print(f"[PASS] 17. Admin Activity Logs Query: Fetched {len(logs)} MongoDB Events")

        # 18. Admin Terminate Suspicious Session
        res = self.client.post(f'/api/admin/sessions/{mon_attempt_id}/terminate', headers=headers)
        self.assertEqual(res.status_code, 200)

        # Confirm heartbeat detects termination
        res = self.client.post('/api/quiz/heartbeat', json={'attempt_id': mon_attempt_id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json['data']['is_terminated'])
        print("[PASS] 18. Admin Live Session Termination & Immediate Student Block")

        # 19. Admin Login Rate Limiting / Brute-force Protection
        test_ip = f"192.168.1.{uuid.uuid4().int % 250}"
        for _ in range(5):
            self.client.post('/api/admin/login', json={'username': 'Admin', 'password': 'WrongPassword!'}, headers={'X-Forwarded-For': test_ip})
        # 6th attempt should be blocked with 429
        blocked_res = self.client.post('/api/admin/login', json={'username': 'Admin', 'password': 'WrongPassword!'}, headers={'X-Forwarded-For': test_ip})
        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn('temporarily locked', blocked_res.json['message'])
        print("[PASS] 19. Admin Login Rate Limiting (HTTP 429 Brute-force Lockout)")

if __name__ == '__main__':
    unittest.main()
