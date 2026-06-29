🤖 ROS2 Jazzy 심화 강의 - Day 33/55
━━━━━━━━━━━━━━━━━━

📚 [주제] 실전 미니 프로젝트 2 - SLAM 구현

📖 이론
SLAM(Simultaneous Localization and Mapping)은 로봇이 동시에 자신의 위치를 추적하고 주변 환경의 지도를 생성하는 기술입니다.ROS2에서는 Cartographer와 Navigation2를 활용하여 SLAM 시스템을 구축할 수 있습니다.

**핵심 개념:**
- Cartographer: 구글 개발의 2D/3D SLAM 라이브러리
- AMCL(Automatic Monte Carlo Localization): 위치 추정 알고리즘
- Particle Filter: 확률론적 위치 추정
- Scan Matching: 라이다 스캔 데이터를 이용한 위치 보정

💻 코드 예시
```python
# SLAM 노드 구현 예시
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped

class SlamNode(Node):
    def __init__(self):
        super().__init__('slam_node')
        
        # QoS 설정
        qos = QoSProfile(depth=10)
        
        # 구독자 설정
        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, qos)
        
        # 퍼블리셔 설정
        self.pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/amcl_pose', qos)
        
        self.get_logger().info('SLAM 노드 시작')
    
    def scan_callback(self, msg):
        """라이다 스캔 데이터 처리"""
        # 1. 데이터 전처리
        ranges = msg.ranges
        
        # 2. 필터링 (무효값 제거)
        valid_ranges = [r for r in ranges if 0.1 < r < 10.0]
        
        # 3. 특징점 추출
        features = self.extract_features(valid_ranges)
        
        # 4. 위치 추정 (Particle Filter 적용)
        estimated_pose = self.estimate_pose(features)
        
        # 5. 위치 정보 발행
        pose_msg = PoseWithCovarianceStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = 'map'
        pose_msg.pose.pose = estimated_pose
        
        self.pose_pub.publish(pose_msg)
    
    def extract_features(self, ranges):
        """특징점 추출 (엣지, 코너 등)"""
        features = []
        
        # 간단한 엣지 검출
        for i in range(1, len(ranges)-1):
            diff = abs(ranges[i-1] - ranges[i+1])
            if diff > 0.5:  # 엣지 임계값
                features.append((i, ranges[i]))
        
        return features
    
    def estimate_pose(self, features):
        """특징점을 이용한 위치 추정"""
        # Particle Filter를 이용한 위치 추정 로직
        # 실제 구현에서는 AMCL 패키지 활용
        estimated_pose = Pose()
        estimated_pose.position.x = 0.0
        estimated_pose.position.y = 0.0
        estimated_pose.position.z = 0.0
        estimated_pose.orientation.x = 0.0
        estimated_pose.orientation.y = 0.0
        estimated_pose.orientation.z = 0.0
        estimated_pose.orientation.w = 1.0
        
        return estimated_pose

def main(args=None):
    rclpy.init(args=args)
    node = SlamNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

📝 오늘의 과제
1. Cartographer 설정 파일(cartographer_ros/configuration.lua) 생성
2. 라이더 데이터 토픽(/scan)을 이용한 SLAM 노드 개발
3. AMCL을 이용한 위치 추정 시뮬레이션 실행
4. RViz에서 지도 생성 및 위치 추적 시각화
5. 생성된 지도(map.pgm)를 YAML 파일로 변환

🎯 다음 시간: 실전 미니 프로젝트 3 - Nav2 내비게이션