import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

const LavaLamp: React.FC = () => {
    // Unified Color palette (matching Chat gradients):
    // Background: Dark Green (#004d40)
    // Orbs: Teal (#26A69A), Deep Teal (#00695C)
    const orbs = [
        {
            color: '#26A69A', // Teal
            initialX: '10%',
            initialY: '10%',
            width: '400px',
            height: '400px',
            duration: 7,
        },
        {
            color: '#00695C', // Deep Teal
            initialX: '80%',
            initialY: '20%',
            width: '350px',
            height: '350px',
            duration: 9,
        },
        {
            color: '#26A69A', // Teal
            initialX: '50%',
            initialY: '50%',
            width: '500px',
            height: '500px',
            duration: 10,
        },
        {
            color: '#00695C', // Deep Teal
            initialX: '20%',
            initialY: '80%',
            width: '300px',
            height: '300px',
            duration: 8,
        },
        {
            color: '#26A69A', // Teal
            initialX: '70%',
            initialY: '70%',
            width: '450px',
            height: '450px',
            duration: 8.5,
        },
        {
            color: '#00695C', // Deep Teal
            initialX: '90%',
            initialY: '10%',
            width: '380px',
            height: '380px',
            duration: 6,
        },
    ];

    return (
        <div className="fixed inset-0 -z-10 overflow-hidden bg-[#004d40]">
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <Sparkles className="w-[600px] h-[600px] text-white opacity-[0.10]" />
            </div>
            <div className="absolute inset-0 backdrop-blur-[100px]" style={{ zIndex: 1 }} />
            {orbs.map((orb, index) => (
                <motion.div
                    key={index}
                    className="absolute rounded-full mix-blend-screen opacity-50"
                    style={{
                        backgroundColor: orb.color,
                        width: orb.width,
                        height: orb.height,
                        left: orb.initialX,
                        top: orb.initialY,
                        willChange: 'transform',
                    }}
                    animate={{
                        x: [0, Math.random() * 300 - 150, Math.random() * 300 - 150, 0],
                        y: [0, Math.random() * 300 - 150, Math.random() * 300 - 150, 0],
                        scale: [1, 1.2, 0.9, 1],
                    }}
                    transition={{
                        duration: orb.duration,
                        repeat: Infinity,
                        repeatType: "mirror",
                        ease: "easeInOut",
                    }}
                />
            ))}
        </div>
    );
};

export default LavaLamp;
